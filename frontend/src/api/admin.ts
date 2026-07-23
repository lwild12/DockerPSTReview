import { apiFetch } from "./client";

export interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
}

export interface SystemSettings {
  enable_api_docs: boolean;
  cookie_secure: boolean;
  updated_at: string;
  updated_by_id: string | null;
}

export async function listAdminUsers(): Promise<AdminUser[]> {
  return apiFetch<AdminUser[]>("/admin/users");
}

export async function updateAdminUser(
  userId: string,
  payload: { is_active?: boolean; is_superuser?: boolean },
): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/admin/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function getSystemSettings(): Promise<SystemSettings> {
  return apiFetch<SystemSettings>("/admin/settings");
}

export async function updateSystemSettings(payload: {
  enable_api_docs?: boolean;
  cookie_secure?: boolean;
}): Promise<SystemSettings> {
  return apiFetch<SystemSettings>("/admin/settings", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
