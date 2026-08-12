"use client";

import { useState } from "react";
import { useFormContext, type FieldPath } from "react-hook-form";
import {
  formatCoords,
  hasValidCoordinates,
  parseGoogleMapsCoords,
  type LocationFields,
} from "@/lib/location-utils";
import type { WizardFormValues } from "@/lib/wizard-schema";
import { TextField } from "./fields";

interface LocationEntryPanelProps {
  /** RHF prefix, e.g. `depots.0` or `manualStops.1`. */
  namePrefix: FieldPath<WizardFormValues>;
}

function fieldPath<T extends FieldPath<WizardFormValues>>(prefix: string, field: string): T {
  return `${prefix}.${field}` as T;
}

export function LocationEntryPanel({ namePrefix }: LocationEntryPanelProps) {
  const { setValue, watch, trigger } = useFormContext<WizardFormValues>();
  const [pasteValue, setPasteValue] = useState("");
  const [pasteError, setPasteError] = useState<string | null>(null);

  const values = watch(namePrefix) as LocationFields | undefined;
  const hasCoords = values ? hasValidCoordinates(values) : false;
  const optionalSuffix = hasCoords ? " (optional)" : "";

  const applyPaste = () => {
    const parsed = parseGoogleMapsCoords(pasteValue);
    if (!parsed.ok) {
      setPasteError(parsed.error);
      return;
    }
    setValue(fieldPath(namePrefix, "latitude"), parsed.latitude, { shouldDirty: true });
    setValue(fieldPath(namePrefix, "longitude"), parsed.longitude, { shouldDirty: true });
    setPasteError(null);
    setPasteValue("");
    void trigger(namePrefix);
  };

  const clearCoords = () => {
    setValue(fieldPath(namePrefix, "latitude"), undefined, { shouldDirty: true });
    setValue(fieldPath(namePrefix, "longitude"), undefined, { shouldDirty: true });
    setPasteError(null);
    void trigger(namePrefix);
  };

  return (
    <div className="location-entry">
      <div className="grid-2">
        <TextField
          name={fieldPath(namePrefix, "address")}
          label={`Street address${optionalSuffix}`}
          placeholder="123 Warehouse Way"
          autoComplete="off"
        />
        <TextField
          name={fieldPath(namePrefix, "address2")}
          label="Address line 2 (optional)"
          placeholder="Suite 100"
        />
        <TextField
          name={fieldPath(namePrefix, "city")}
          label={`City${optionalSuffix}`}
          placeholder="Denver"
        />
        <TextField
          name={fieldPath(namePrefix, "state")}
          label={`State${optionalSuffix}`}
          placeholder="CO"
        />
        <TextField
          name={fieldPath(namePrefix, "zip")}
          label={`ZIP${optionalSuffix}`}
          placeholder="80202"
        />
      </div>

      <div className="field">
        <label htmlFor={`${String(namePrefix)}-coords-paste`}>
          Coordinates (optional)
        </label>
        <p className="field-hint">
          In Google Maps, right-click the pin and choose Copy coordinates, then paste here.
        </p>
        <div className="location-actions">
          <input
            id={`${String(namePrefix)}-coords-paste`}
            type="text"
            value={pasteValue}
            placeholder="38.38080520110032, -97.4279212147894"
            autoComplete="off"
            onChange={(event) => {
              setPasteValue(event.target.value);
              if (pasteError) setPasteError(null);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                applyPaste();
              }
            }}
          />
          <button type="button" className="secondary" onClick={applyPaste}>
            Use coordinates
          </button>
          {hasCoords ? (
            <button type="button" className="link-button" onClick={clearCoords}>
              Clear coordinates
            </button>
          ) : null}
        </div>
      </div>

      {pasteError ? (
        <p className="field-error" role="alert">
          {pasteError}
        </p>
      ) : null}

      {hasCoords ? (
        <p className="field-hint">
          Coordinates: {formatCoords(values!.latitude!, values!.longitude!)}
        </p>
      ) : (
        <p className="field-hint">Coordinates are optional. Leave blank if you do not have them.</p>
      )}
    </div>
  );
}
