import { z } from "zod";
import type { DayLetter, PatternScope } from "./wizard-types";

/**
 * Zod is the single source of truth for wizard validation. Schemas mirror the
 * backend Pydantic constraints (`backend/schemas/*.py`) so most errors are
 * caught client-side before submit; the backend remains the authority and its
 * 422s are mapped back onto these same fields (see `lib/api.ts`).
 */

// Mirrors backend `_validate_ascii`: ASCII only, no tabs or line breaks.
export const isAsciiText = (value: string): boolean => {
  for (let i = 0; i < value.length; i += 1) {
    const code = value.charCodeAt(i);
    if (code > 127) return false;
    if (code === 9 || code === 10 || code === 13) return false;
  }
  return true;
};

const ASCII_MESSAGE = "Use standard characters only (no accents, tabs, or line breaks)";

const requiredAscii = z.string().trim().min(1, "Required").refine(isAsciiText, ASCII_MESSAGE);
const optionalAscii = z.string().refine(isAsciiText, ASCII_MESSAGE);

/** Treat empty string / null / NaN as "absent" before applying an optional number rule. */
const optionalNum = <T extends z.ZodTypeAny>(inner: T) =>
  z.preprocess(
    (v) =>
      v === "" || v === null || v === undefined || (typeof v === "number" && Number.isNaN(v))
        ? undefined
        : v,
    inner.optional(),
  );

const depotSchema = z.object({
  address: requiredAscii,
  city: requiredAscii,
  state: requiredAscii,
  zip: requiredAscii,
  trucks: z.coerce.number().int("Whole number of trucks").gt(0, "Need at least 1 truck"),
});

const volumeSchema = z.object({
  name: requiredAscii,
  capacity: z.coerce.number().gt(0, "Capacity must be greater than 0"),
});

const volumeAnswerSchema = z.object({
  name: z.string(),
  mode: z.enum(["fixed", "averaged"]),
  value: z.coerce.number().gt(0, "Must be greater than 0"),
});

const truckStep = z.object({
  weeks: z.coerce.number().int("Whole number of weeks").gt(0, "Must be at least 1 week"),
  depots: z.array(depotSchema).min(1, "Add at least one depot"),
  volumes: z.array(volumeSchema).min(1, "Add at least one volume"),
  miCost: z.coerce.number().min(0, "Must be 0 or more"),
  hrCost: z.coerce.number().min(0, "Must be 0 or more"),
  fixedCost: z.coerce.number().min(0, "Must be 0 or more"),
  maxWork: z.coerce.number().gt(0, "Must be greater than 0"),
  maxDrive: z.coerce.number().gt(0, "Must be greater than 0"),
  preTrip: z.coerce.number().int("Whole number of minutes").min(0, "Must be 0 or more"),
  postTrip: z.coerce.number().int("Whole number of minutes").min(0, "Must be 0 or more"),
  spEq: optionalAscii,
  seed: z.coerce.number().int("Whole number").min(0, "Must be 0 or more"),
});

const stopStep = z.object({
  selectionMode: z.enum(["radius", "state"]),
  radiusMiles: optionalNum(z.coerce.number().gt(0, "Radius must be greater than 0")),
  states: z.string().default(""),
  stopCount: z.coerce.number().int("Whole number of stops").gt(0, "Must be at least 1 stop"),
  fixedTimeMinutes: z.coerce.number().gt(0, "Must be greater than 0"),
  volumeAnswers: z.array(volumeAnswerSchema).min(1, "Answer each volume"),
  frequencyValues: z.array(z.number()).min(1, "Select at least one frequency"),
  timeWindowMode: z.enum(["fixed", "randomized"]),
  open1: optionalNum(z.coerce.number().int("Use 24h time, e.g. 800").min(0).max(2359, "Max 2359")),
  close1: optionalNum(z.coerce.number().int("Use 24h time, e.g. 1700").min(0).max(2359, "Max 2359")),
  patternScope: z.enum(["week", "weekday", "weekend", "random", "specific_days"]),
  specificDays: z.array(z.enum(["S", "M", "T", "W", "R", "F", "A"])).default([]),
  eqCodeEnabled: z.boolean().default(false),
  eqCodes: z.string().default(""),
  eqFraction: optionalNum(z.coerce.number().gt(0, "Between 0 and 1").max(1, "Between 0 and 1")),
  consolidationEnabled: z.boolean().default(false),
  linesPerCustomer: optionalNum(
    z.coerce.number().int("Whole number").gt(1, "Must be greater than 1").max(20, "20 or fewer"),
  ),
  aliasesEnabled: z.boolean().default(false),
  aliasName: optionalAscii,
  aliasContact: optionalAscii,
  aliasPhone: optionalAscii,
  aliasId1: optionalAscii,
  aliasId2: optionalAscii,
  aliasId3: optionalAscii,
  aliasAddress2: optionalAscii,
});

const minutesOf = (military: number): number =>
  Math.floor(military / 100) * 60 + (military % 100);

/** Mirrors backend `validate_time_window`: in range and wide enough for FixedTime. */
export const isValidTimeWindow = (open1: number, close1: number, fixedTime: number): boolean => {
  if (!(open1 >= 0 && open1 <= close1 && close1 <= 2359)) return false;
  return minutesOf(close1) - minutesOf(open1) >= fixedTime;
};

export const parseStates = (raw: string): string[] =>
  raw
    .split(",")
    .map((s) => s.trim().toUpperCase())
    .filter((s) => s.length > 0);

export const parseCsv = (raw: string): string[] =>
  raw
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);

export const wizardSchema = truckStep.merge(stopStep).superRefine((data, ctx) => {
  // Unique volume names (backend TruckConfig.volume_names_unique).
  const seen = new Set<string>();
  data.volumes.forEach((vol, index) => {
    if (seen.has(vol.name)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Volume names must be unique",
        path: ["volumes", index, "name"],
      });
    }
    seen.add(vol.name);
  });

  // Selection mode conditionals (backend SelectionConfig.mode_matches_fields).
  if (data.selectionMode === "radius" && data.radiusMiles == null) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Enter a radius for radius-based selection",
      path: ["radiusMiles"],
    });
  }
  if (data.selectionMode === "state" && parseStates(data.states).length === 0) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Enter at least one state code (e.g. UT, NV)",
      path: ["states"],
    });
  }

  // Fixed time window (backend TimeWindowConfig + StopConfig.fixed_time_window_is_valid).
  if (data.timeWindowMode === "fixed") {
    if (data.open1 == null || data.close1 == null) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Set both open and close times for a fixed window",
        path: [data.open1 == null ? "open1" : "close1"],
      });
    } else if (!isValidTimeWindow(data.open1, data.close1, data.fixedTimeMinutes)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Window must span at least the stop service time and have open ≤ close",
        path: ["close1"],
      });
    }
  }

  if (data.patternScope === "specific_days" && data.specificDays.length === 0) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Pick at least one day",
      path: ["specificDays"],
    });
  }

  if (data.eqCodeEnabled && parseCsv(data.eqCodes).length === 0) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Enter at least one equipment code",
      path: ["eqCodes"],
    });
  }

  if (data.consolidationEnabled && data.linesPerCustomer == null) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Enter lines per customer (2–20)",
      path: ["linesPerCustomer"],
    });
  }
});

export interface DepotFormValue {
  address: string;
  city: string;
  state: string;
  zip: string;
  trucks: number;
}

export interface VolumeFormValue {
  name: string;
  capacity: number;
}

export interface VolumeAnswerFormValue {
  name: string;
  mode: "fixed" | "averaged";
  value: number;
}

/**
 * Form value shape. Hand-maintained rather than `z.infer<typeof wizardSchema>`
 * on purpose: `z.coerce`/`z.preprocess` give the schema awkward input-vs-output
 * types (and optional-via-preprocess fields infer as required keys with
 * `| undefined` rather than optional keys), which fights RHF's defaultValues.
 * The step-field arrays below are kept in lockstep with these keys by the
 * compile-time coverage guard at the end of this file, so a field added here
 * without updating a step array (or vice-versa) is a type error.
 */
export interface WizardFormValues {
  // Route (truck) step
  weeks: number;
  depots: DepotFormValue[];
  volumes: VolumeFormValue[];
  miCost: number;
  hrCost: number;
  fixedCost: number;
  maxWork: number;
  maxDrive: number;
  preTrip: number;
  postTrip: number;
  spEq: string;
  seed: number;
  // Stop step
  selectionMode: "radius" | "state";
  radiusMiles?: number;
  states: string;
  stopCount: number;
  fixedTimeMinutes: number;
  volumeAnswers: VolumeAnswerFormValue[];
  frequencyValues: number[];
  timeWindowMode: "fixed" | "randomized";
  open1?: number;
  close1?: number;
  patternScope: PatternScope;
  specificDays: DayLetter[];
  eqCodeEnabled: boolean;
  eqCodes: string;
  eqFraction?: number;
  consolidationEnabled: boolean;
  linesPerCustomer?: number;
  aliasesEnabled: boolean;
  aliasName: string;
  aliasContact: string;
  aliasPhone: string;
  aliasId1: string;
  aliasId2: string;
  aliasId3: string;
  aliasAddress2: string;
}

export const defaultWizardValues: WizardFormValues = {
  weeks: 2,
  depots: [{ address: "", city: "", state: "", zip: "", trucks: 5 }],
  volumes: [{ name: "Cases", capacity: 2000 }],
  miCost: 1.39,
  hrCost: 30.0,
  fixedCost: 250.0,
  maxWork: 14,
  maxDrive: 11,
  preTrip: 15,
  postTrip: 30,
  spEq: "",
  seed: 0,
  selectionMode: "radius",
  radiusMiles: 50,
  states: "",
  stopCount: 20,
  fixedTimeMinutes: 10,
  volumeAnswers: [{ name: "Cases", mode: "averaged", value: 40 }],
  frequencyValues: [1],
  timeWindowMode: "randomized",
  open1: 800,
  close1: 1700,
  patternScope: "week",
  specificDays: [],
  eqCodeEnabled: false,
  eqCodes: "",
  eqFraction: 0.25,
  consolidationEnabled: false,
  linesPerCustomer: 3,
  aliasesEnabled: false,
  aliasName: "",
  aliasContact: "",
  aliasPhone: "",
  aliasId1: "",
  aliasId2: "",
  aliasId3: "",
  aliasAddress2: "",
};

export const truckStepFields = [
  "weeks",
  "depots",
  "volumes",
  "miCost",
  "hrCost",
  "fixedCost",
  "maxWork",
  "maxDrive",
  "preTrip",
  "postTrip",
  "spEq",
  "seed",
] as const;

export const stopStepFields = [
  "selectionMode",
  "radiusMiles",
  "states",
  "stopCount",
  "fixedTimeMinutes",
  "volumeAnswers",
  "frequencyValues",
  "timeWindowMode",
  "open1",
  "close1",
  "patternScope",
  "specificDays",
  "eqCodeEnabled",
  "eqCodes",
  "eqFraction",
  "consolidationEnabled",
  "linesPerCustomer",
  "aliasesEnabled",
  "aliasName",
  "aliasContact",
  "aliasPhone",
  "aliasId1",
  "aliasId2",
  "aliasId3",
  "aliasAddress2",
] as const;

// Compile-time drift guard: the two step arrays must together name every key of
// WizardFormValues exactly (no stray names, no missing keys). If the schema and
// interface gain a field but a step array doesn't, or a name is mistyped, one of
// these assignments stops compiling — keeping per-step trigger()/routing honest.
type StepFieldName = (typeof truckStepFields)[number] | (typeof stopStepFields)[number];
const _stepFieldsAreKeys: StepFieldName extends keyof WizardFormValues ? true : never = true;
const _keysAreStepFields: keyof WizardFormValues extends StepFieldName ? true : never = true;
void _stepFieldsAreKeys;
void _keysAreStepFields;
