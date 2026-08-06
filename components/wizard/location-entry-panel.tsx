"use client";

import { useState } from "react";
import { useFormContext, type FieldPath } from "react-hook-form";
import {
  appendLocation,
  geocodeLocation,
  LocationDuplicateError,
} from "@/lib/api";
import {
  formatCoords,
  hasValidCoordinates,
  normalizeAddressKey,
  type LocationFields,
} from "@/lib/location-utils";
import type { WizardFormValues } from "@/lib/wizard-schema";
import { NumberField, TextField } from "./fields";

interface LocationEntryPanelProps {
  /** RHF prefix, e.g. `depots.0` or `manualStops.1`. */
  namePrefix: FieldPath<WizardFormValues>;
  /** Addresses already added this session (normalized keys). */
  sessionKeys: Set<string>;
  onSessionKeyAdded: (key: string) => void;
  showTrucksField?: false;
}

function fieldPath<T extends FieldPath<WizardFormValues>>(prefix: string, field: string): T {
  return `${prefix}.${field}` as T;
}

export function LocationEntryPanel({
  namePrefix,
  sessionKeys,
  onSessionKeyAdded,
}: LocationEntryPanelProps) {
  const { getValues, setValue, watch } = useFormContext<WizardFormValues>();
  const [geocodeError, setGeocodeError] = useState<string | null>(null);
  const [geocoding, setGeocoding] = useState(false);
  const [persisting, setPersisting] = useState(false);
  const [persistMessage, setPersistMessage] = useState<string | null>(null);
  const [duplicatePrompt, setDuplicatePrompt] = useState<{
    message: string;
    latitude: number;
    longitude: number;
    existingName: string;
  } | null>(null);

  const values = watch(namePrefix) as LocationFields | undefined;
  const showManualCoords = values?.showManualCoords ?? false;
  const inLocationDb = values?.inLocationDb ?? false;
  const geoSource = values?.geoSource ?? null;
  const hasCoords = values ? hasValidCoordinates(values) : false;

  const readFields = (): LocationFields => getValues(namePrefix) as LocationFields;

  const setField = (field: keyof LocationFields, value: unknown) => {
    setValue(fieldPath(namePrefix, field), value as never, { shouldDirty: true });
  };

  const handleGeocode = async () => {
    setGeocodeError(null);
    setPersistMessage(null);
    const loc = readFields();
    if (loc.geoSource === "manual") return;

    setGeocoding(true);
    try {
      const result = await geocodeLocation({
        address: loc.address.trim(),
        city: loc.city.trim(),
        state: loc.state.trim(),
        zip: loc.zip.trim(),
      });
      setValue(fieldPath(namePrefix, "latitude"), result.latitude, { shouldDirty: true });
      setValue(fieldPath(namePrefix, "longitude"), result.longitude, { shouldDirty: true });
      setValue(fieldPath(namePrefix, "geoSource"), "api", { shouldDirty: true });
      setValue(fieldPath(namePrefix, "showManualCoords"), true, { shouldDirty: true });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Could not find coordinates for this address";
      setGeocodeError(message);
    } finally {
      setGeocoding(false);
    }
  };

  const applyPersistedCoords = (latitude: number, longitude: number, label: string) => {
    setValue(fieldPath(namePrefix, "latitude"), latitude, { shouldDirty: true });
    setValue(fieldPath(namePrefix, "longitude"), longitude, { shouldDirty: true });
    setValue(fieldPath(namePrefix, "inLocationDb"), true, { shouldDirty: true });
    setValue(fieldPath(namePrefix, "showManualCoords"), true, { shouldDirty: true });
    setPersistMessage(label);
    setDuplicatePrompt(null);
  };

  const persistLocation = async (forceReuse = false) => {
    setGeocodeError(null);
    setPersistMessage(null);
    const loc = readFields();
    if (!hasValidCoordinates(loc)) {
      setGeocodeError("Enter valid coordinates before adding to the database");
      return;
    }

    const key = normalizeAddressKey(loc.address, loc.city, loc.state, loc.zip);
    if (!forceReuse && sessionKeys.has(key)) {
      setDuplicatePrompt({
        message: "This address was already added in this wizard session.",
        latitude: loc.latitude!,
        longitude: loc.longitude!,
        existingName: "session",
      });
      return;
    }

    setPersisting(true);
    try {
      const result = await appendLocation({
        address: loc.address.trim(),
        address2: (loc.address2 ?? "").trim(),
        city: loc.city.trim(),
        state: loc.state.trim(),
        zip: loc.zip.trim(),
        latitude: loc.latitude!,
        longitude: loc.longitude!,
      });
      applyPersistedCoords(
        result.latitude,
        result.longitude,
        `Added as ${result.name} (${result.id1})`,
      );
      onSessionKeyAdded(key);
    } catch (error) {
      if (error instanceof LocationDuplicateError) {
        setDuplicatePrompt({
          message: error.duplicate.message,
          latitude: error.duplicate.latitude,
          longitude: error.duplicate.longitude,
          existingName: error.duplicate.existing_name,
        });
        return;
      }
      setGeocodeError(error instanceof Error ? error.message : "Could not save location");
    } finally {
      setPersisting(false);
    }
  };

  const handleManualCoordChange = () => {
    if (geoSource !== "manual") {
      setValue(fieldPath(namePrefix, "geoSource"), "manual", { shouldDirty: true });
    }
  };

  return (
    <div className="location-entry">
      <div className="grid-2">
        <TextField
          name={fieldPath(namePrefix, "address")}
          label="Street address"
          placeholder="123 Warehouse Way"
          autoComplete="off"
        />
        <TextField
          name={fieldPath(namePrefix, "address2")}
          label="Address line 2 (optional)"
          placeholder="Suite 100"
        />
        <TextField name={fieldPath(namePrefix, "city")} label="City" placeholder="Denver" />
        <TextField name={fieldPath(namePrefix, "state")} label="State" placeholder="CO" />
        <TextField name={fieldPath(namePrefix, "zip")} label="ZIP" placeholder="80202" />
      </div>

      <div className="location-actions">
        <button
          type="button"
          className="secondary"
          disabled={geocoding || geoSource === "manual"}
          onClick={() => void handleGeocode()}
        >
          {geocoding ? "Looking up…" : "Look up coordinates"}
        </button>
        <button
          type="button"
          className="link-button"
          onClick={() => {
            const next = !showManualCoords;
            setField("showManualCoords", next);
            if (next) setField("geoSource", "manual");
          }}
        >
          {showManualCoords ? "Hide manual coordinates" : "Enter coordinates manually"}
        </button>
      </div>

      {geocodeError ? (
        <p className="field-error" role="alert">
          {geocodeError}
        </p>
      ) : null}

      {showManualCoords ? (
        <div className="grid-2">
          <NumberField
            name={fieldPath(namePrefix, "latitude")}
            label="Latitude"
            hint="WGS84, -90 to 90"
            min={-90}
            max={90}
            step="any"
          />
          <NumberField
            name={fieldPath(namePrefix, "longitude")}
            label="Longitude"
            hint="WGS84, -180 to 180"
            min={-180}
            max={180}
            step="any"
          />
        </div>
      ) : null}

      {hasCoords ? (
        <p className="field-hint">
          Coordinates: {formatCoords(values!.latitude!, values!.longitude!)}
          {geoSource === "api" ? " (geocoded)" : geoSource === "manual" ? " (manual)" : ""}
          {inLocationDb ? " — in location database" : ""}
        </p>
      ) : null}

      {hasCoords && !inLocationDb ? (
        <button
          type="button"
          className="secondary"
          disabled={persisting}
          onClick={() => void persistLocation()}
        >
          {persisting ? "Saving…" : "Add to location database"}
        </button>
      ) : null}

      {persistMessage ? <p className="field-hint">{persistMessage}</p> : null}

      {duplicatePrompt ? (
        <div className="location-duplicate" role="alert">
          <p>{duplicatePrompt.message}</p>
          <p className="field-hint">
            Existing record: {duplicatePrompt.existingName} at{" "}
            {formatCoords(duplicatePrompt.latitude, duplicatePrompt.longitude)}
          </p>
          <div className="location-actions">
            <button
              type="button"
              className="secondary"
              onClick={() =>
                applyPersistedCoords(
                  duplicatePrompt.latitude,
                  duplicatePrompt.longitude,
                  `Reusing existing coordinates from ${duplicatePrompt.existingName}`,
                )
              }
            >
              Reuse existing record
            </button>
            <button
              type="button"
              className="link-button"
              onClick={() => setDuplicatePrompt(null)}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
