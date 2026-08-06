import { describe, expect, it, vi } from "vitest";
import {
  appendLocation,
  geocodeLocation,
  LocationDuplicateError,
} from "./api";

describe("geocodeLocation", () => {
  it("returns coordinates on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        json: async () => ({
          latitude: 39.7392,
          longitude: -104.9903,
          formatted_address: "Denver, CO",
          provider: "trimble-single-search",
        }),
      })) as unknown as typeof fetch,
    );

    const result = await geocodeLocation({
      address: "1 Main St",
      city: "Denver",
      state: "CO",
      zip: "80202",
    });
    expect(result.latitude).toBe(39.7392);
    expect(result.provider).toBe("trimble-single-search");
  });
});

describe("appendLocation", () => {
  it("throws LocationDuplicateError on 409", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 409,
        json: async () => ({
          detail: {
            existing_name: "Customer 00001",
            existing_id1: "000001",
            latitude: 39.0,
            longitude: -105.0,
            message: "duplicate",
          },
        }),
      })) as unknown as typeof fetch,
    );

    await expect(
      appendLocation({
        address: "1 Main St",
        city: "Denver",
        state: "CO",
        zip: "80202",
        latitude: 39.0,
        longitude: -105.0,
      }),
    ).rejects.toBeInstanceOf(LocationDuplicateError);
  });
});
