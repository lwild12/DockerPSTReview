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
  registration_enabled: boolean;
  oidc_enabled: boolean;
  oidc_issuer_url: string;
  oidc_client_id: string;
  oidc_client_secret_set: boolean;
  oidc_display_name: string;
  ollama_base_url: string;
  ollama_model: string;
  ollama_api_key_set: boolean;
  ai_review_concurrency: number;
  ollama_log_requests: boolean;
  updated_at: string;
  updated_by_id: string | null;
}

export interface SystemSettingsUpdate {
  enable_api_docs?: boolean;
  cookie_secure?: boolean;
  registration_enabled?: boolean;
  oidc_enabled?: boolean;
  oidc_issuer_url?: string;
  oidc_client_id?: string;
  oidc_client_secret?: string;
  oidc_display_name?: string;
  ollama_base_url?: string;
  ollama_model?: string;
  ollama_api_key?: string;
  ai_review_concurrency?: number;
  ollama_log_requests?: boolean;
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

export async function updateSystemSettings(
  payload: SystemSettingsUpdate,
): Promise<SystemSettings> {
  return apiFetch<SystemSettings>("/admin/settings", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
