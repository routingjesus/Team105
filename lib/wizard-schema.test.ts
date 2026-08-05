import { describe, expect, it } from "vitest";
import {
  defaultWizardValues,
  isValidTimeWindow,
  parseStates,
  parseCsv,
  wizardSchema,
  type WizardFormValues,
} from "./wizard-schema";

const validValues: WizardFormValues = {
  ...defaultWizardValues,
  depots: [{ address: "1 Warehouse Way", city: "Salt Lake City", state: "UT", zip: "84101", trucks: 5 }],
};

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

  it("accepts blank ID2/ID3 aliases", () => {
    const result = wizardSchema.safeParse({ ...validValues, aliasId2: "", aliasId3: "" });
    expect(result.success).toBe(true);
  });

  it("rejects non-ASCII ID2/ID3 aliases", () => {
    const result = wizardSchema.safeParse({ ...validValues, aliasId2: "Zöne" });
    expect(result.success).toBe(false);
  });
});
