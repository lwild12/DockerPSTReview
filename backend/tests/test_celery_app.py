from pathlib import Path

from app.celery_app import celery_app


def test_all_task_modules_are_registered_with_celery():
    """Every app/tasks/*.py module that defines a @celery_app.task must be
    listed in celery_app's `include` -- that's how a real worker process
    (which never imports app.tasks.* on its own) discovers tasks to
    register. A module missing from `include` still works in-process
    (e.g. in tests, which import task modules directly), but a live
    worker rejects its tasks as unregistered and silently discards them."""
    tasks_dir = Path(__file__).resolve().parent.parent / "app" / "tasks"
    included = set(celery_app.conf.include)
    for path in sorted(tasks_dir.glob("*.py")):
        if path.stem == "__init__":
            continue
        source = path.read_text()
        if "@celery_app.task" not in source:
            continue
        module_name = f"app.tasks.{path.stem}"
        assert module_name in included, (
            f"{module_name} defines a Celery task but is missing from "
            "celery_app's `include` list in app/celery_app.py"
        )
