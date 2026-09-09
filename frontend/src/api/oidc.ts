import { API_BASE, apiFetch } from "./client";

export interface OidcPublicConfig {
  enabled: boolean;
  display_name?: string;
}

export async function getOidcPublicConfig(): Promise<OidcPublicConfig> {
  return apiFetch<OidcPublicConfig>("/auth/oidc/config");
}

export function oidcLoginUrl(): string {
  return `${API_BASE}/auth/oidc/login`;
}
