/** Shared helpers for manual location entry (SPEC-017). */

export type GeoSource = "api" | "manual" | null;

export interface LocationFields {
  address: string;
  address2: string;
  city: string;
  state: string;
  zip: string;
  latitude?: number;
  longitude?: number;
  geoSource?: GeoSource;
  inLocationDb: boolean;
  showManualCoords: boolean;
}

export const emptyLocationFields = (): LocationFields => ({
  address: "",
  address2: "",
  city: "",
  state: "",
  zip: "",
  latitude: undefined,
  longitude: undefined,
  geoSource: null,
  inLocationDb: false,
  showManualCoords: false,
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
  return latitude >= -90 && latitude <= 90 && longitude >= -180 && longitude <= 180;
}

export function formatCoords(latitude: number, longitude: number): string {
  return `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`;
}
