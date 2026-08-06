import { describe, expect, it } from "vitest";
import { hasValidCoordinates, normalizeAddressKey } from "./location-utils";

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
});
