import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  apiLocToFormPath,
  base64ToBlob,
  downloadBlob,
  generateStops,
  generateTruck,
  stepForFormPath,
} from "./api";
import type { StopConfig, TruckConfig } from "./wizard-types";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const truckConfig = {} as TruckConfig;
const stopConfig = {} as StopConfig;

describe("apiLocToFormPath", () => {
  it("maps top-level and nested backend fields to form paths", () => {
    expect(apiLocToFormPath(["body", "weeks"])).toBe("weeks");
    expect(apiLocToFormPath(["body", "depots", 0, "address"])).toBe("depots.0.address");
    expect(apiLocToFormPath(["body", "volume_answers", 1, "value"])).toBe("volumeAnswers.1.value");
    expect(apiLocToFormPath(["body", "selection", "mode"])).toBe("selectionMode");
    expect(apiLocToFormPath(["body", "time_window", "open1"])).toBe("open1");
    expect(apiLocToFormPath(["body", "stop_count"])).toBe("stopCount");
  });

  it("returns null for model-level or unknown locations", () => {
    expect(apiLocToFormPath(["body"])).toBeNull();
    expect(apiLocToFormPath(["body", "mystery_field"])).toBeNull();
  });
});

describe("stepForFormPath", () => {
  it("classifies fields by owning step", () => {
    expect(stepForFormPath("weeks")).toBe(0);
    expect(stepForFormPath("depots.0.address")).toBe(0);
    expect(stepForFormPath("stopCount")).toBe(1);
    expect(stepForFormPath("open1")).toBe(1);
    expect(stepForFormPath("nope")).toBeNull();
  });
});

describe("base64ToBlob", () => {
  it("decodes base64 content into a typed blob", async () => {
    const blob = base64ToBlob("aGVsbG8=", "text/plain");
    expect(blob.type).toBe("text/plain");
    expect(await blob.text()).toBe("hello");
  });
});

describe("generateTruck / generateStops", () => {
  it("posts JSON to the truck endpoint and returns parsed metadata", async () => {
    const payload = { filename: "fleet.truck", truck_file_base64: "AAAA" };
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => payload,
    })) as unknown as typeof fetch;
    vi.stubGlobal("fetch", fetchMock);

    const result = await generateTruck(truckConfig);
    expect(result).toEqual(payload);
    const [url, init] = (fetchMock as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(String(url)).toMatch(/\/api\/trucks\/generate$/);
    expect((init as RequestInit).method).toBe("POST");
  });

  it("maps a 422 detail array onto field errors", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: false,
      status: 422,
      json: async () => ({
        detail: [{ loc: ["body", "weeks"], msg: "must be > 0", type: "value_error" }],
      }),
    })) as unknown as typeof fetch;
    vi.stubGlobal("fetch", fetchMock);

    await expect(generateStops(stopConfig)).rejects.toMatchObject({
      status: 422,
    });
    try {
      await generateStops(stopConfig);
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).fieldErrors).toEqual([
        { path: "weeks", message: "must be > 0" },
      ]);
    }
  });

  it("carries a string 422 detail as a root message", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: false,
      status: 422,
      json: async () => ({ detail: "Depot could not be geocoded" }),
    })) as unknown as typeof fetch;
    vi.stubGlobal("fetch", fetchMock);

    try {
      await generateTruck(truckConfig);
      throw new Error("expected rejection");
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).rootMessage).toBe("Depot could not be geocoded");
      expect((error as ApiError).fieldErrors).toEqual([]);
    }
  });
});

describe("downloadBlob", () => {
  it("creates an object URL and clicks an anchor", () => {
    const createSpy = vi.fn(() => "blob:mock");
    const revokeSpy = vi.fn();
    vi.stubGlobal("URL", { ...URL, createObjectURL: createSpy, revokeObjectURL: revokeSpy });
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);

    downloadBlob(new Blob(["x"], { type: "text/plain" }), "out.txt");

    expect(createSpy).toHaveBeenCalledTimes(1);
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(revokeSpy).toHaveBeenCalledTimes(1);
  });
});
