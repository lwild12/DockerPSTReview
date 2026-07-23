import { apiFetch } from "./client";

export interface OidcPublicConfig {
  enabled: boolean;
  display_name?: string;
}

export async function getOidcPublicConfig(): Promise<OidcPublicConfig> {
  return apiFetch<OidcPublicConfig>("/auth/oidc/config");
}

export function oidcLoginUrl(): string {
  const base = import.meta.env.VITE_API_BASE_URL ?? "/api";
  return `${base}/auth/oidc/login`;
}
