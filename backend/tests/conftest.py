from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db import Base, get_db
from app.main import app

settings = get_settings()


def _test_database_url(base_url: str) -> tuple[str, str]:
    """Derive an isolated `<db>_test` URL so tests never touch the dev database."""
    parts = urlsplit(base_url)
    db_name = parts.path.lstrip("/") + "_test"
    return urlunsplit(parts._replace(path=f"/{db_name}")), db_name


TEST_DATABASE_URL, TEST_DB_NAME = _test_database_url(settings.database_url)


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def _ensure_test_database():
    parts = urlsplit(settings.database_url.replace("postgresql+asyncpg://", "postgresql://"))
    conn = await asyncpg.connect(
        user=parts.username,
        password=parts.password,
        host=parts.hostname,
        port=parts.port or 5432,
        database="postgres",
    )
    try:
        await conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    except asyncpg.exceptions.DuplicateDatabaseError:
        pass
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def db_engine():
    # Fresh engine per test, bound to the current test's event loop, to avoid
    # asyncpg connections leaking across pytest-asyncio's per-test event loops.
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_engine):
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def register_and_login(
    client: AsyncClient, email: str, password: str = "SuperSecret123!", full_name: str = ""
) -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    login_resp = await client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
    )
    assert login_resp.status_code == 204, login_resp.text
    me = await client.get("/api/auth/users/me")
    assert me.status_code == 200, me.text
    return me.json()
