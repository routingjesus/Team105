import type { WizardFormValues } from "@/lib/wizard-schema";

/**
 * Session-scoped persistence for in-progress wizard answers. Demo hardening:
 * a mid-flow refresh keeps the user's answers; a successful generation clears
 * them. Not durable across browser restarts (out of scope per the spec).
 */
const STORAGE_KEY = "team105.dataset-wizard.v1";

const hasStorage = (): boolean =>
  typeof window !== "undefined" && typeof window.sessionStorage !== "undefined";

export function loadPersistedValues(): Partial<WizardFormValues> | null {
  if (!hasStorage()) return null;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Partial<WizardFormValues>) : null;
  } catch {
    return null;
  }
}

export function persistValues(values: WizardFormValues): void {
  if (!hasStorage()) return;
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(values));
  } catch {
    // Ignore quota / serialization errors — persistence is best-effort.
  }
}

export function clearPersistedValues(): void {
  if (!hasStorage()) return;
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore.
  }
}
