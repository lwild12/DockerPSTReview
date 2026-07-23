import { apiFetch } from "./client";

export interface User {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
  full_name: string;
}

export async function login(email: string, password: string): Promise<void> {
  const body = new URLSearchParams({ username: email, password });
  await apiFetch<void>("/auth/login", { method: "POST", body });
}

export async function logout(): Promise<void> {
  await apiFetch<void>("/auth/logout", { method: "POST" });
}

export async function register(
  email: string,
  password: string,
  fullName: string,
): Promise<User> {
  return apiFetch<User>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, full_name: fullName }),
  });
}

export async function getCurrentUser(): Promise<User> {
  return apiFetch<User>("/auth/users/me");
}
