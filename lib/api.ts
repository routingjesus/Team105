import type {
  FastApiErrorBody,
  FastApiValidationDetail,
  StopConfig,
  StopGenerationResponse,
  TruckConfig,
  TruckGenerationResponse,
} from "./wizard-types";
import { stopStepFields, truckStepFields } from "./wizard-schema";

/**
 * Resolve the base URL that `postJson`/`downloadFile` prepend to each `/api/...`
 * path. An empty, unset, or whitespace-only `NEXT_PUBLIC_API_BASE_URL` yields
 * `""`, so requests hit relative paths (e.g. `/api/trucks/generate`) and flow
 * through the Next.js same-origin proxy — no host prefix, no CORS. An explicit
 * absolute value targets that origin directly (existing behavior). The trailing
 * slash is stripped so callers can safely concatenate a leading-slash path.
 *
 * Note: `||`, not `??` — `??` would treat an explicit empty string as a set
 * value, but proxy mode needs empty/whitespace/unset to all collapse to `""`.
 */
export function resolveApiBaseUrl(
  raw: string | undefined = process.env.NEXT_PUBLIC_API_BASE_URL,
): string {
  return (raw || "").trim().replace(/\/$/, "");
}

export const API_BASE_URL = resolveApiBaseUrl();

export const TRUCK_MIME = "text/tab-separated-values";
export const STOP_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

export interface FieldError {
  /** RHF field path (dot/bracket notation). */
  path: string;
  message: string;
}

/** A generation failure with backend errors mapped back onto form fields. */
export class ApiError extends Error {
  readonly status: number;
  readonly fieldErrors: FieldError[];
  readonly rootMessage?: string;

  constructor(status: number, fieldErrors: FieldError[], rootMessage?: string) {
    super(rootMessage ?? fieldErrors[0]?.message ?? `Request failed (${status})`);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
    this.rootMessage = rootMessage;
  }
}

// snake_case API field -> camelCase form field (top level).
const TOP_LEVEL_MAP: Record<string, string> = {
  weeks: "weeks",
  depots: "depots",
  volumes: "volumes",
  mi_cost: "miCost",
  hr_cost: "hrCost",
  fixed_cost: "fixedCost",
  max_work: "maxWork",
  max_drive: "maxDrive",
  pre_trip: "preTrip",
  post_trip: "postTrip",
  sp_eq: "spEq",
  seed: "seed",
  stop_count: "stopCount",
  fixed_time_minutes: "fixedTimeMinutes",
  volume_answers: "volumeAnswers",
  frequency_values: "frequencyValues",
  specific_days: "specificDays",
};

// Nested API objects the form flattens into top-level fields.
const NESTED_MAP: Record<string, Record<string, string>> = {
  selection: { mode: "selectionMode", radius_miles: "radiusMiles", states: "states" },
  time_window: {
    mode: "timeWindowMode",
    open1: "open1",
    close1: "close1",
    pattern_scope: "patternScope",
    specific_days: "specificDays",
  },
  eq_code: { codes: "eqCodes", fraction: "eqFraction", enabled: "eqCodeEnabled" },
  consolidation: { lines_per_customer: "linesPerCustomer", enabled: "consolidationEnabled" },
};

/** Translate a FastAPI validation `loc` into an RHF form path, or null if unmapped. */
export function apiLocToFormPath(loc: (string | number)[]): string | null {
  const parts = loc[0] === "body" ? loc.slice(1) : [...loc];
  if (parts.length === 0) return null;

  const [head, ...rest] = parts;
  if (typeof head !== "string") return null;

  if (NESTED_MAP[head]) {
    const sub = rest[0];
    if (typeof sub === "string" && NESTED_MAP[head][sub]) {
      return NESTED_MAP[head][sub];
    }
    return null;
  }

  const mappedHead = TOP_LEVEL_MAP[head];
  if (!mappedHead) return null;

  // Arrays (depots/volumes/volume_answers) keep their index + subfield.
  const tail = rest.map((p) => `.${p}`).join("");
  return `${mappedHead}${tail}`;
}

/** Which wizard step (0 = route, 1 = stop) owns a form path; null if unknown. */
export function stepForFormPath(path: string): 0 | 1 | null {
  const head = path.split(/[.[]/)[0];
  if ((truckStepFields as readonly string[]).includes(head)) return 0;
  if ((stopStepFields as readonly string[]).includes(head)) return 1;
  return null;
}

async function parseErrorBody(response: Response): Promise<ApiError> {
  let body: FastApiErrorBody | null = null;
  try {
    body = (await response.json()) as FastApiErrorBody;
  } catch {
    body = null;
  }

  const detail = body?.detail;

  if (typeof detail === "string") {
    return new ApiError(response.status, [], detail);
  }

  if (Array.isArray(detail)) {
    const fieldErrors: FieldError[] = [];
    const rootMessages: string[] = [];
    for (const item of detail as FastApiValidationDetail[]) {
      const path = apiLocToFormPath(item.loc);
      if (path) {
        fieldErrors.push({ path, message: item.msg });
      } else {
        rootMessages.push(item.msg);
      }
    }
    return new ApiError(
      response.status,
      fieldErrors,
      rootMessages.length > 0 ? rootMessages.join("; ") : undefined,
    );
  }

  return new ApiError(
    response.status,
    [],
    `The server rejected the request (HTTP ${response.status}).`,
  );
}

async function postJson<T>(path: string, payload: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (cause) {
    throw new ApiError(
      0,
      [],
      `Could not reach the generation service at ${API_BASE_URL}. Is the backend running?`,
    );
  }

  if (!response.ok) {
    throw await parseErrorBody(response);
  }

  return (await response.json()) as T;
}

export function generateTruck(config: TruckConfig): Promise<TruckGenerationResponse> {
  return postJson<TruckGenerationResponse>("/api/trucks/generate", config);
}

export function generateStops(config: StopConfig): Promise<StopGenerationResponse> {
  return postJson<StopGenerationResponse>("/api/stops/generate", config);
}

/** Decode base64 file content (from a `generate` response) into a Blob. */
export function base64ToBlob(base64: string, mimeType: string): Blob {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new Blob([bytes], { type: mimeType });
}

/** Trigger a browser download for a Blob (single user gesture, popup-safe). */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

/** Convenience: decode base64 content and download it in one call. */
export function downloadBase64(base64: string, filename: string, mimeType: string): void {
  downloadBlob(base64ToBlob(base64, mimeType), filename);
}

/** Extract a filename from a `Content-Disposition` header, if present. */
export function parseContentDispositionFilename(header: string | null): string | null {
  if (!header) return null;
  const utf8 = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8) return decodeURIComponent(utf8[1]);
  const plain = header.match(/filename="?([^";]+)"?/i);
  return plain ? plain[1] : null;
}

/**
 * Alternative to the base64-in-JSON path: POST to a `.../download` endpoint and
 * stream the raw file bytes to a download. Guards on `response.ok` and reuses
 * the same 422 → field-error mapping as the JSON endpoints.
 */
export async function downloadFile(
  path: string,
  config: unknown,
  fallbackName: string,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
  } catch {
    throw new ApiError(
      0,
      [],
      `Could not reach the generation service at ${API_BASE_URL}. Is the backend running?`,
    );
  }

  if (!response.ok) {
    throw await parseErrorBody(response);
  }

  const blob = await response.blob();
  const filename =
    parseContentDispositionFilename(response.headers.get("Content-Disposition")) ?? fallbackName;
  downloadBlob(blob, filename);
}
