import { parseCsv, parseStates, type WizardFormValues } from "./wizard-schema";
import type {
  AliasConfig,
  StopConfig,
  TruckConfig,
  TruckGenerationResponse,
} from "./wizard-types";

/** Map wizard form values to the exact `TruckConfig` request body. */
export function buildTruckConfig(values: WizardFormValues): TruckConfig {
  return {
    weeks: values.weeks,
    depots: values.depots.map((d) => ({
      address: d.address.trim(),
      city: d.city.trim(),
      state: d.state.trim(),
      zip: d.zip.trim(),
      trucks: d.trucks,
    })),
    mi_cost: values.miCost,
    hr_cost: values.hrCost,
    fixed_cost: values.fixedCost,
    max_work: values.maxWork,
    max_drive: values.maxDrive,
    pre_trip: values.preTrip,
    post_trip: values.postTrip,
    sp_eq: values.spEq.trim(),
    volumes: values.volumes.map((v) => ({ name: v.name.trim(), capacity: v.capacity })),
    seed: values.seed,
  };
}

function buildAliases(values: WizardFormValues): AliasConfig | null {
  const clean = (v: string) => (v.trim().length > 0 ? v.trim() : null);
  // ID2/ID3 have their own always-visible prompt (SPEC-010) and are sent
  // whenever non-blank, independent of the "Rename output columns" toggle
  // that still gates the other five alias fields.
  const aliases: AliasConfig = {
    name: values.aliasesEnabled ? clean(values.aliasName) : null,
    contact: values.aliasesEnabled ? clean(values.aliasContact) : null,
    phone: values.aliasesEnabled ? clean(values.aliasPhone) : null,
    id1: values.aliasesEnabled ? clean(values.aliasId1) : null,
    id2: clean(values.aliasId2),
    id3: clean(values.aliasId3),
    address_2: values.aliasesEnabled ? clean(values.aliasAddress2) : null,
  };
  const hasAny = Object.values(aliases).some((v) => v !== null);
  return hasAny ? aliases : null;
}

/**
 * Map wizard form values to the exact `StopConfig` request body.
 *
 * Depots, weeks, and volumes come from the truck `generate` response
 * (`TruckGenerationResponse`) so the two files stay contract-consistent — the
 * backend sequences stop generation on the truck config output.
 */
export function buildStopConfig(
  values: WizardFormValues,
  truck: TruckGenerationResponse,
): StopConfig {
  const config: StopConfig = {
    depots: truck.depots,
    weeks: truck.weeks,
    volumes: truck.volume_names,
    selection: {
      mode: values.selectionMode,
      radius_miles: values.selectionMode === "radius" ? (values.radiusMiles ?? null) : null,
      states: values.selectionMode === "state" ? parseStates(values.states) : null,
    },
    stop_count: values.stopCount,
    fixed_time_minutes: values.fixedTimeMinutes,
    volume_answers: values.volumeAnswers.map((a) => ({
      name: a.name,
      mode: a.mode,
      value: a.value,
    })),
    frequency_values: values.frequencyValues,
    time_window: {
      mode: values.timeWindowMode,
      open1: values.timeWindowMode === "fixed" ? (values.open1 ?? null) : null,
      close1: values.timeWindowMode === "fixed" ? (values.close1 ?? null) : null,
      pattern_scope: values.patternScope,
      specific_days:
        values.patternScope === "specific_days" && values.specificDays.length > 0
          ? values.specificDays
          : null,
    },
    eq_code: values.eqCodeEnabled
      ? { enabled: true, codes: parseCsv(values.eqCodes), fraction: values.eqFraction ?? 0.25 }
      : null,
    consolidation:
      values.consolidationEnabled && values.linesPerCustomer != null
        ? { enabled: true, lines_per_customer: values.linesPerCustomer }
        : null,
    aliases: buildAliases(values),
    seed: values.seed,
  };
  return config;
}
