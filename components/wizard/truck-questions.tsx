"use client";

import { useMemo, useState } from "react";
import { useFieldArray, useFormContext } from "react-hook-form";
import { normalizeAddressKey } from "@/lib/location-utils";
import type { WizardFormValues } from "@/lib/wizard-schema";
import { NumberField, TextField } from "./fields";
import { LocationEntryPanel } from "./location-entry-panel";

/**
 * "Route details" step. Deliberately framed as route/fleet setup — the file
 * type being built (the .TRUCK file) is never surfaced to the user (AC 1).
 */
export function TruckQuestions() {
  const { control, getFieldState, formState, watch } = useFormContext<WizardFormValues>();
  const depots = useFieldArray({ control, name: "depots" });
  const volumes = useFieldArray({ control, name: "volumes" });
  const [sessionKeys, setSessionKeys] = useState<Set<string>>(() => new Set());
  const depotValues = watch("depots");

  const sessionKeySet = useMemo(() => {
    const keys = new Set(sessionKeys);
    for (const depot of depotValues ?? []) {
      if (depot.inLocationDb) {
        keys.add(normalizeAddressKey(depot.address, depot.city, depot.state, depot.zip));
      }
    }
    return keys;
  }, [depotValues, sessionKeys]);

  const depotsError = getFieldState("depots", formState).error;
  const volumesError = getFieldState("volumes", formState).error;

  return (
    <section aria-labelledby="wizard-step-heading">
      <h2 id="wizard-step-heading" tabIndex={-1}>
        Route details
      </h2>
      <p className="step-intro">
        Tell us about the delivery operation you want to model — the depots, how many trucks run
        from each, and the planning horizon.
      </p>

      <NumberField
        name="weeks"
        label="Planning weeks"
        hint="How many weeks of routing to build. Dispatch days = weeks × 7."
        min={1}
        step={1}
      />

      <fieldset className="group">
        <legend>Depots</legend>
        {depotsError?.message ? (
          <p className="field-error" role="alert">
            {depotsError.message}
          </p>
        ) : null}
        {depots.fields.map((field, index) => (
          <div className="repeat-row" key={field.id}>
            <div className="repeat-row-header">
              <h3>Depot {index + 1}</h3>
              {depots.fields.length > 1 ? (
                <button
                  type="button"
                  className="link-button"
                  onClick={() => depots.remove(index)}
                >
                  Remove
                </button>
              ) : null}
            </div>
            <LocationEntryPanel
              namePrefix={`depots.${index}`}
              sessionKeys={sessionKeySet}
              onSessionKeyAdded={(key) => setSessionKeys((prev) => new Set(prev).add(key))}
            />
            <NumberField
              name={`depots.${index}.trucks`}
              label="Trucks at this depot"
              min={1}
              step={1}
            />
          </div>
        ))}
        <button
          type="button"
          className="secondary"
          onClick={() =>
            depots.append({
              address: "",
              address2: "",
              city: "",
              state: "",
              zip: "",
              trucks: 5,
              latitude: undefined,
              longitude: undefined,
              geoSource: null,
              inLocationDb: false,
              showManualCoords: false,
            })
          }
        >
          + Add depot
        </button>
      </fieldset>

      <fieldset className="group">
        <legend>Volumes</legend>
        <p className="field-hint">
          Named capacity dimensions each truck carries (e.g. Cases, Weight). You&apos;ll set how
          stops consume these next.
        </p>
        {volumesError?.message ? (
          <p className="field-error" role="alert">
            {volumesError.message}
          </p>
        ) : null}
        {volumes.fields.map((field, index) => (
          <div className="repeat-row" key={field.id}>
            <div className="repeat-row-header">
              <h3>Volume {index + 1}</h3>
              {volumes.fields.length > 1 ? (
                <button
                  type="button"
                  className="link-button"
                  onClick={() => volumes.remove(index)}
                >
                  Remove
                </button>
              ) : null}
            </div>
            <div className="grid-2">
              <TextField name={`volumes.${index}.name`} label="Name" placeholder="Cases" />
              <NumberField
                name={`volumes.${index}.capacity`}
                label="Per-truck capacity"
                min={0}
                step="any"
              />
            </div>
          </div>
        ))}
        <button
          type="button"
          className="secondary"
          onClick={() => volumes.append({ name: "", capacity: 1000 })}
        >
          + Add volume
        </button>
      </fieldset>

      <details className="advanced">
        <summary>Costs &amp; work rules (optional)</summary>
        <div className="grid-2">
          <NumberField name="miCost" label="Cost per mile ($)" min={0} step="any" />
          <NumberField name="hrCost" label="Cost per hour ($)" min={0} step="any" />
          <NumberField name="fixedCost" label="Fixed cost per truck ($)" min={0} step="any" />
          <NumberField name="maxWork" label="Max work time (hours)" min={0} step="any" />
          <NumberField name="maxDrive" label="Max drive time (hours)" min={0} step="any" />
          <NumberField name="preTrip" label="Pre-trip (minutes)" min={0} step={1} />
          <NumberField name="postTrip" label="Post-trip (minutes)" min={0} step={1} />
          <TextField
            name="spEq"
            label="Special equipment code"
            hint="Applied to all trucks. Leave blank for none."
          />
          <NumberField
            name="seed"
            label="Random seed"
            hint="Same seed → same dataset. Use for reproducible demos."
            min={0}
            step={1}
          />
        </div>
      </details>
    </section>
  );
}
