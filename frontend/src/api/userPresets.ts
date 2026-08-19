import { apiFetch } from "./client";

export interface TagPreset {
  id: string;
  name: string;
  color: string;
  created_at: string;
}

export interface RedactionReasonPreset {
  id: string;
  reason: string;
  created_at: string;
}

export async function listTagPresets(): Promise<TagPreset[]> {
  return apiFetch<TagPreset[]>("/me/tag-presets");
}

export async function deleteTagPreset(presetId: string): Promise<void> {
  await apiFetch<void>(`/me/tag-presets/${presetId}`, { method: "DELETE" });
}

export async function listRedactionReasonPresets(): Promise<RedactionReasonPreset[]> {
  return apiFetch<RedactionReasonPreset[]>("/me/redaction-reason-presets");
}

export async function deleteRedactionReasonPreset(presetId: string): Promise<void> {
  await apiFetch<void>(`/me/redaction-reason-presets/${presetId}`, { method: "DELETE" });
}
