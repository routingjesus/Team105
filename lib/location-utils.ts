/** Shared helpers for wizard location entry (session coords; no geocode/persist). */

export interface LocationFields {
  address: string;
  address2?: string;
  city: string;
  state: string;
  zip: string;
  latitude?: number;
  longitude?: number;
}

/** Empty location with address2 set so RHF field-array append matches form values. */
export const emptyLocationFields = (): LocationFields & { address2: string } => ({
  address: "",
  address2: "",
  city: "",
  state: "",
  zip: "",
  latitude: undefined,
  longitude: undefined,
});

export function normalizeAddressKey(
  address: string,
  city: string,
  state: string,
  zip: string,
): string {
  return [address, city, state, zip]
    .map((part) => part.trim().toLowerCase())
    .join("|");
}

export function hasValidCoordinates(loc: LocationFields): boolean {
  const { latitude, longitude } = loc;
  if (latitude == null || longitude == null || Number.isNaN(latitude) || Number.isNaN(longitude)) {
    return false;
  }
  if (latitude === 0 && longitude === 0) return false;
  return latitude >= -90 && latitude <= 90 && longitude >= -180 && longitude <= 180;
}

/** True when street, city, state, and ZIP are all non-empty after trim. */
export function hasCompleteAddress(
  loc: Pick<LocationFields, "address" | "city" | "state" | "zip">,
): boolean {
  return [loc.address, loc.city, loc.state, loc.zip].every((part) => part.trim().length > 0);
}

export function formatCoords(latitude: number, longitude: number): string {
  return `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`;
}

export type CoordsParseResult =
  | { ok: true; latitude: number; longitude: number }
  | { ok: false; error: string };

/**
 * Parse Google Maps "copy coordinates" decimal paste (`lat, long`).
 * Rejects DMS, partial tokens, out-of-bounds, and Null Island (0, 0).
 */
export function parseGoogleMapsCoords(raw: string): CoordsParseResult {
  let text = raw.trim();
  if (!text) {
    return { ok: false, error: "Paste latitude and longitude (e.g. 38.38, -97.42)" };
  }
  if (text.startsWith("(") && text.endsWith(")")) {
    text = text.slice(1, -1).trim();
  }
  if (/[°′″'"NSEWnsew]/.test(text)) {
    return {
      ok: false,
      error: "Use decimal degrees from Google Maps (not degrees/minutes/seconds)",
    };
  }
  const sep = text.includes(",") ? "," : text.includes(";") ? ";" : null;
  if (!sep) {
    return { ok: false, error: "Expected two numbers separated by a comma" };
  }
  const parts = text.split(sep).map((p) => p.trim());
  if (parts.length !== 2 || parts[0] === "" || parts[1] === "") {
    return { ok: false, error: "Expected latitude and longitude (two numbers)" };
  }
  const latitude = Number(parts[0]);
  const longitude = Number(parts[1]);
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    return { ok: false, error: "Coordinates must be decimal numbers" };
  }
  if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) {
    return { ok: false, error: "Coordinates are outside valid WGS84 bounds" };
  }
  if (latitude === 0 && longitude === 0) {
    return { ok: false, error: "Coordinates (0, 0) are not allowed" };
  }
  return { ok: true, latitude, longitude };
}
