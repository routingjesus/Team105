"use client";

import { useEffect } from "react";
import { useController, useFieldArray, useFormContext, useWatch } from "react-hook-form";
import {
  DAY_LABELS,
  DAY_LETTERS,
  FREQUENCY_LABELS,
  FREQUENCY_VALUES,
  type DayLetter,
} from "@/lib/wizard-types";
import type { WizardFormValues } from "@/lib/wizard-schema";
import { NumberField, TextField } from "./fields";

/**
 * "Stop details" step. Continues the same flow as the route step with no phase
 * announcement and no mention of the .XLSX stop file being built (AC 2).
 */
export function StopQuestions() {
  const { control, register, getFieldState, getValues, formState } =
    useFormContext<WizardFormValues>();

  const selectionMode = useWatch({ control, name: "selectionMode" });
  const timeWindowMode = useWatch({ control, name: "timeWindowMode" });
  const patternScope = useWatch({ control, name: "patternScope" });
  const eqCodeEnabled = useWatch({ control, name: "eqCodeEnabled" });
  const consolidationEnabled = useWatch({ control, name: "consolidationEnabled" });
  const aliasesEnabled = useWatch({ control, name: "aliasesEnabled" });
  const volumes = useWatch({ control, name: "volumes" });

  const volumeAnswers = useFieldArray({ control, name: "volumeAnswers" });
  const namesKey = (volumes ?? []).map((v) => v?.name ?? "").join("|");

  // Keep one volume answer per named volume, preserving existing answers by name.
  useEffect(() => {
    const names = (volumes ?? [])
      .map((v) => v?.name ?? "")
      .filter((n) => n.trim().length > 0);
    const current = getValues("volumeAnswers") ?? [];
    const next = names.map(
      (name) =>
        current.find((a) => a.name === name) ?? {
          name,
          mode: "averaged" as const,
          value: 40,
        },
    );
    const changed =
      next.length !== current.length || next.some((a, i) => current[i]?.name !== a.name);
    if (changed) volumeAnswers.replace(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [namesKey]);

  const frequency = useController({ control, name: "frequencyValues" });
  const frequencyError = getFieldState("frequencyValues", formState).error;
  const toggleFrequency = (value: number) => {
    const current = new Set<number>(frequency.field.value ?? []);
    if (current.has(value)) current.delete(value);
    else current.add(value);
    frequency.field.onChange([...current]);
  };

  const specificDays = useController({ control, name: "specificDays" });
  const specificDaysError = getFieldState("specificDays", formState).error;
  const toggleDay = (day: DayLetter) => {
    const current = new Set<DayLetter>(specificDays.field.value ?? []);
    if (current.has(day)) current.delete(day);
    else current.add(day);
    specificDays.field.onChange([...current]);
  };

  return (
    <section aria-labelledby="wizard-step-heading">
      <h2 id="wizard-step-heading" tabIndex={-1}>
        Stop details
      </h2>
      <p className="step-intro">
        Now describe the customer stops these routes serve — where they come from, how often they
        get service, and their delivery windows.
      </p>

      <fieldset className="group">
        <legend>Where do stops come from?</legend>
        <div className="radio-row">
          <label>
            <input type="radio" value="radius" {...register("selectionMode")} /> Within a radius of
            the depots
          </label>
          <label>
            <input type="radio" value="state" {...register("selectionMode")} /> In specific states
          </label>
        </div>
        {selectionMode === "radius" ? (
          <NumberField
            name="radiusMiles"
            label="Radius (miles)"
            hint="Stops are drawn from candidates within this distance of a depot."
            min={0}
            step="any"
          />
        ) : (
          <TextField
            name="states"
            label="States"
            hint="Comma-separated 2-letter codes, e.g. UT, NV, ID."
            placeholder="UT, NV"
          />
        )}
      </fieldset>

      <div className="grid-2">
        <NumberField
          name="stopCount"
          label="Number of stops"
          hint="Target stop count in the generated dataset."
          min={1}
          step={1}
        />
        <NumberField
          name="fixedTimeMinutes"
          label="Service time per stop (minutes)"
          min={0}
          step="any"
        />
      </div>

      <fieldset className="group">
        <legend>How much does each stop consume?</legend>
        {volumeAnswers.fields.map((field, index) => (
          <div className="repeat-row" key={field.id}>
            <div className="repeat-row-header">
              <h3>{field.name || `Volume ${index + 1}`}</h3>
            </div>
            <div className="grid-2">
              <div className="field">
                <label htmlFor={`volumeAnswers-${index}-mode`}>Mode</label>
                <select
                  id={`volumeAnswers-${index}-mode`}
                  {...register(`volumeAnswers.${index}.mode`)}
                >
                  <option value="averaged">Averaged around a target</option>
                  <option value="fixed">Fixed value on every stop</option>
                </select>
              </div>
              <NumberField
                name={`volumeAnswers.${index}.value`}
                label="Value"
                min={0}
                step="any"
              />
            </div>
          </div>
        ))}
      </fieldset>

      <fieldset className="group" aria-describedby={frequencyError ? "frequency-error" : undefined}>
        <legend>Service frequency</legend>
        <p className="field-hint">How often stops are visited. Pick all that should appear.</p>
        <div className="checkbox-grid">
          {FREQUENCY_VALUES.map((value) => {
            const key = String(value);
            return (
              <label key={key} className="checkbox">
                <input
                  type="checkbox"
                  checked={(frequency.field.value ?? []).includes(value)}
                  onChange={() => toggleFrequency(value)}
                />
                {FREQUENCY_LABELS[key] ?? key}
              </label>
            );
          })}
        </div>
        {frequencyError?.message ? (
          <p className="field-error" role="alert" id="frequency-error">
            {frequencyError.message}
          </p>
        ) : null}
      </fieldset>

      <fieldset className="group">
        <legend>Delivery time windows</legend>
        <div className="radio-row">
          <label>
            <input type="radio" value="randomized" {...register("timeWindowMode")} /> Randomized
            windows
          </label>
          <label>
            <input type="radio" value="fixed" {...register("timeWindowMode")} /> One fixed window
          </label>
        </div>
        {timeWindowMode === "fixed" ? (
          <div className="grid-2">
            <NumberField
              name="open1"
              label="Opens (24h, e.g. 800)"
              min={0}
              max={2359}
              step={1}
            />
            <NumberField
              name="close1"
              label="Closes (24h, e.g. 1700)"
              min={0}
              max={2359}
              step={1}
            />
          </div>
        ) : null}
        <div className="field">
          <label htmlFor="patternScope">Which days can stops be served?</label>
          <select id="patternScope" {...register("patternScope")}>
            <option value="week">Any day of the week</option>
            <option value="weekday">Weekdays only</option>
            <option value="weekend">Weekends only</option>
            <option value="random">Random days</option>
            <option value="specific_days">Specific days I choose</option>
          </select>
        </div>
        {patternScope === "specific_days" ? (
          <div className="checkbox-grid" role="group" aria-label="Specific days">
            {DAY_LETTERS.map((day) => (
              <label key={day} className="checkbox">
                <input
                  type="checkbox"
                  checked={(specificDays.field.value ?? []).includes(day)}
                  onChange={() => toggleDay(day)}
                />
                {DAY_LABELS[day]}
              </label>
            ))}
            {specificDaysError?.message ? (
              <p className="field-error" role="alert">
                {specificDaysError.message}
              </p>
            ) : null}
          </div>
        ) : null}
      </fieldset>

      <details className="advanced">
        <summary>Advanced stop options (optional)</summary>

        <div className="advanced-block">
          <label className="checkbox">
            <input type="checkbox" {...register("eqCodeEnabled")} /> Assign equipment codes to some
            stops
          </label>
          {eqCodeEnabled ? (
            <div className="grid-2">
              <TextField
                name="eqCodes"
                label="Equipment codes"
                hint="Comma-separated, e.g. LIFT, DOCK."
                placeholder="LIFT, DOCK"
              />
              <NumberField
                name="eqFraction"
                label="Fraction of stops (0–1)"
                min={0}
                max={1}
                step="any"
              />
            </div>
          ) : null}
        </div>

        <div className="advanced-block">
          <label className="checkbox">
            <input type="checkbox" {...register("consolidationEnabled")} /> Add multiple line items
            per customer
          </label>
          {consolidationEnabled ? (
            <NumberField
              name="linesPerCustomer"
              label="Lines per customer (2–20)"
              min={2}
              max={20}
              step={1}
            />
          ) : null}
        </div>

        <div className="advanced-block">
          <label className="checkbox">
            <input type="checkbox" {...register("aliasesEnabled")} /> Rename output columns
          </label>
          {aliasesEnabled ? (
            <div className="grid-2">
              <TextField name="aliasName" label="Name column alias" />
              <TextField name="aliasContact" label="Contact column alias" />
              <TextField name="aliasPhone" label="Phone column alias" />
              <TextField name="aliasId1" label="ID1 column alias" />
              <TextField name="aliasId2" label="ID2 column alias" />
              <TextField name="aliasId3" label="ID3 column alias" />
              <TextField name="aliasAddress2" label="Address 2 column alias" />
            </div>
          ) : null}
        </div>
      </details>
    </section>
  );
}
