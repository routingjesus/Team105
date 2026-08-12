import { describe, expect, it } from "vitest";
import {
  defaultWizardValues,
  isValidTimeWindow,
  parseStates,
  parseCsv,
  parseZips,
  ZipParseError,
  wizardSchema,
  type WizardFormValues,
} from "./wizard-schema";

const validValues: WizardFormValues = {
  ...defaultWizardValues,
  depots: [{ ...defaultWizardValues.depots[0], address: "1 Warehouse Way", city: "Salt Lake City", state: "UT", zip: "84101" }],
  selectionMode: "state",
  states: "UT",
};

const PASTE_COORDS = {
  latitude: 38.38080520110032,
  longitude: -97.4279212147894,
};

const blankAddress = { address: "", address2: "", city: "", state: "", zip: "" };

function requiredPaths(result: ReturnType<typeof wizardSchema.safeParse>): string[] {
  if (result.success) return [];
  return result.error.issues.filter((issue) => issue.message === "Required").map((issue) => issue.path.join("."));
}

describe("isValidTimeWindow", () => {
  it("accepts a window wide enough for the service time", () => {
    expect(isValidTimeWindow(800, 1700, 10)).toBe(true);
    expect(isValidTimeWindow(800, 900, 60)).toBe(true);
  });

  it("rejects inverted or too-narrow windows", () => {
    expect(isValidTimeWindow(1700, 800, 10)).toBe(false);
    expect(isValidTimeWindow(800, 830, 60)).toBe(false);
    expect(isValidTimeWindow(-1, 100, 10)).toBe(false);
  });
});

describe("parseStates / parseCsv", () => {
  it("splits, trims, uppercases states and drops empties", () => {
    expect(parseStates("ut, nv ,, id")).toEqual(["UT", "NV", "ID"]);
  });
  it("splits csv preserving case", () => {
    expect(parseCsv("LIFT, dock ,")).toEqual(["LIFT", "dock"]);
  });
});

describe("parseZips", () => {
  it("parses singles, ranges, ZIP+4, and leading zeros", () => {
    const zips = parseZips("84101, 67861-67942, 08001-1234, 801");
    expect(zips).toContain("84101");
    expect(zips).toContain("67861");
    expect(zips).toContain("67942");
    expect(zips).toContain("08001");
    expect(zips).toContain("00801");
  });

  it("rejects inverted ranges", () => {
    expect(() => parseZips("67942-67861")).toThrow(ZipParseError);
  });
});

describe("wizardSchema", () => {
  it("accepts a fully valid dataset", () => {
    expect(wizardSchema.safeParse(validValues).success).toBe(true);
  });

  it("requires weeks > 0", () => {
    const result = wizardSchema.safeParse({ ...validValues, weeks: 0 });
    expect(result.success).toBe(false);
  });

  it("requires a depot address", () => {
    const result = wizardSchema.safeParse({
      ...validValues,
      depots: [{ ...validValues.depots[0], address: "" }],
    });
    expect(result.success).toBe(false);
    expect(requiredPaths(result)).toContain("depots.0.address");
  });

  it("accepts a coords-only depot", () => {
    const result = wizardSchema.safeParse({
      ...validValues,
      depots: [{ ...validValues.depots[0], ...blankAddress, ...PASTE_COORDS }],
    });
    expect(result.success).toBe(true);
  });

  it("accepts a coords-only manual stop", () => {
    const result = wizardSchema.safeParse({
      ...validValues,
      manualStops: [{ ...blankAddress, ...PASTE_COORDS }],
    });
    expect(result.success).toBe(true);
  });

  it("accepts a depot with both address and coordinates", () => {
    const result = wizardSchema.safeParse({
      ...validValues,
      depots: [{ ...validValues.depots[0], ...PASTE_COORDS }],
    });
    expect(result.success).toBe(true);
  });

  it("rejects a depot with neither coordinates nor a complete address", () => {
    const result = wizardSchema.safeParse({
      ...validValues,
      depots: [{ ...validValues.depots[0], ...blankAddress }],
    });
    expect(result.success).toBe(false);
    expect(requiredPaths(result)).toEqual(
      expect.arrayContaining(["depots.0.address", "depots.0.city", "depots.0.state", "depots.0.zip"]),
    );
  });

  it("rejects a manual stop with neither coordinates nor a complete address", () => {
    const result = wizardSchema.safeParse({
      ...validValues,
      manualStops: [{ ...blankAddress }],
    });
    expect(result.success).toBe(false);
    expect(requiredPaths(result)).toEqual(
      expect.arrayContaining([
        "manualStops.0.address",
        "manualStops.0.city",
        "manualStops.0.state",
        "manualStops.0.zip",
      ]),
    );
  });

  it("rejects a partial address without coordinates", () => {
    const result = wizardSchema.safeParse({
      ...validValues,
      depots: [{ ...validValues.depots[0], city: "", zip: "" }],
    });
    expect(result.success).toBe(false);
    expect(requiredPaths(result)).toEqual(expect.arrayContaining(["depots.0.city", "depots.0.zip"]));
    expect(requiredPaths(result)).not.toContain("depots.0.address");
  });

  it("does not treat Null Island as coordinates", () => {
    const result = wizardSchema.safeParse({
      ...validValues,
      depots: [{ ...validValues.depots[0], ...blankAddress, latitude: 0, longitude: 0 }],
    });
    expect(result.success).toBe(false);
    expect(requiredPaths(result)).toEqual(
      expect.arrayContaining(["depots.0.address", "depots.0.city", "depots.0.state", "depots.0.zip"]),
    );
  });

  it("rejects non-ASCII depot text", () => {
    const result = wizardSchema.safeParse({
      ...validValues,
      depots: [{ ...validValues.depots[0], city: "Zürich" }],
    });
    expect(result.success).toBe(false);
  });

  it("requires at least one frequency", () => {
    const result = wizardSchema.safeParse({ ...validValues, frequencyValues: [] });
    expect(result.success).toBe(false);
  });

  it("rejects an invalid fixed time window", () => {
    const result = wizardSchema.safeParse({
      ...validValues,
      timeWindowMode: "fixed",
      open1: 1700,
      close1: 800,
    });
    expect(result.success).toBe(false);
  });

  it("requires states when selection mode is state", () => {
    const result = wizardSchema.safeParse({
      ...validValues,
      selectionMode: "state",
      states: "",
    });
    expect(result.success).toBe(false);
  });

  it("requires a radius when selection mode is radius", () => {
    const result = wizardSchema.safeParse({
      ...validValues,
      selectionMode: "radius",
      radiusMiles: undefined,
    });
    expect(result.success).toBe(false);
  });

  it("requires zips when selection mode is zip", () => {
    const result = wizardSchema.safeParse({
      ...validValues,
      selectionMode: "zip",
      zips: "",
    });
    expect(result.success).toBe(false);
  });

  it("accepts zip mode with a valid list", () => {
    const result = wizardSchema.safeParse({
      ...validValues,
      selectionMode: "zip",
      zips: "84101, 67861-67942",
    });
    expect(result.success).toBe(true);
  });

  it("accepts blank ID2/ID3 aliases", () => {
    const result = wizardSchema.safeParse({ ...validValues, aliasId2: "", aliasId3: "" });
    expect(result.success).toBe(true);
  });

  it("rejects non-ASCII ID2/ID3 aliases", () => {
    expect(wizardSchema.safeParse({ ...validValues, aliasId2: "Zöne" }).success).toBe(false);
    expect(wizardSchema.safeParse({ ...validValues, aliasId3: "Zöne" }).success).toBe(false);
  });
});
