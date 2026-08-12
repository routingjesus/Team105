import { describe, expect, it } from "vitest";
import {
  hasValidCoordinates,
  normalizeAddressKey,
  parseGoogleMapsCoords,
} from "./location-utils";

describe("normalizeAddressKey", () => {
  it("casefolds and trims address parts", () => {
    expect(normalizeAddressKey(" 123 Main ", "Denver", "co", "80202 ")).toBe(
      "123 main|denver|co|80202",
    );
  });
});

describe("hasValidCoordinates", () => {
  it("accepts valid WGS84 coordinates", () => {
    expect(
      hasValidCoordinates({
        address: "a",
        city: "b",
        state: "c",
        zip: "d",
        latitude: 39.7,
        longitude: -104.9,
      }),
    ).toBe(true);
  });

  it("rejects out-of-range latitude", () => {
    expect(
      hasValidCoordinates({
        address: "a",
        city: "b",
        state: "c",
        zip: "d",
        latitude: 95,
        longitude: -104.9,
      }),
    ).toBe(false);
  });

  it("rejects Null Island", () => {
    expect(
      hasValidCoordinates({
        address: "a",
        city: "b",
        state: "c",
        zip: "d",
        latitude: 0,
        longitude: 0,
      }),
    ).toBe(false);
  });
});

describe("parseGoogleMapsCoords", () => {
  it("parses the canonical Google Maps paste example", () => {
    const result = parseGoogleMapsCoords("38.38080520110032, -97.4279212147894");
    expect(result).toEqual({
      ok: true,
      latitude: 38.38080520110032,
      longitude: -97.4279212147894,
    });
  });

  it("accepts whitespace and wrapping parentheses", () => {
    const result = parseGoogleMapsCoords("  ( 40.0 , -74.0 )  ");
    expect(result).toEqual({ ok: true, latitude: 40, longitude: -74 });
  });

  it("rejects DMS", () => {
    const result = parseGoogleMapsCoords(`38°22'50.9"N, 97°25'40.5"W`);
    expect(result.ok).toBe(false);
  });

  it("rejects partial tokens", () => {
    expect(parseGoogleMapsCoords("38.38").ok).toBe(false);
    expect(parseGoogleMapsCoords("38.38,").ok).toBe(false);
  });

  it("rejects Null Island and out-of-bounds", () => {
    expect(parseGoogleMapsCoords("0, 0").ok).toBe(false);
    expect(parseGoogleMapsCoords("95, -104").ok).toBe(false);
  });
});
