"use client";

import { useCallback, useState } from "react";
import {
  downloadBase64,
  downloadFile,
  DRPROJECT_CONFIG_MIME,
  STOP_MIME,
  TRUCK_MIME,
} from "@/lib/api";
import { DATASET_ZIP_FILENAME, downloadDatasetZip } from "@/lib/zip";
import { isAsciiText } from "@/lib/wizard-schema";
import type {
  DrprojectConfigResponse,
  StopConfig,
  StopGenerationResponse,
  TruckGenerationResponse,
} from "@/lib/wizard-types";
import { FormRow } from "./fields";

const ASCII_MESSAGE = "Use standard characters only (no accents, tabs, or line breaks)";

interface DownloadProps {
  truck: TruckGenerationResponse;
  stop: StopGenerationResponse;
  drprojectConfig: DrprojectConfigResponse;
  stopConfig: StopConfig;
  onReset: () => void;
}

export function Download({ truck, stop, drprojectConfig, stopConfig, onReset }: DownloadProps) {
  const [branch, setBranch] = useState("");
  const [branchError, setBranchError] = useState<string | undefined>();
  const [csvBusy, setCsvBusy] = useState(false);
  const [csvError, setCsvError] = useState<string | undefined>();
  const [zipError, setZipError] = useState<string | undefined>();

  const handleDownloadAll = useCallback(() => {
    setZipError(undefined);
    try {
      downloadDatasetZip([
        { filename: truck.filename, base64: truck.truck_file_base64 },
        { filename: stop.filename, base64: stop.stop_file_base64, alreadyCompressed: true },
        {
          filename: drprojectConfig.filename,
          base64: drprojectConfig.drproject_config_file_base64,
        },
      ]);
    } catch (error) {
      setZipError((error as Error).message || `Could not prepare ${DATASET_ZIP_FILENAME}.`);
    }
  }, [truck, stop, drprojectConfig]);

  const handleCsvDownload = useCallback(async () => {
    const trimmed = branch.trim();
    if (!trimmed) {
      setBranchError("Required");
      return;
    }
    if (!isAsciiText(trimmed)) {
      setBranchError(ASCII_MESSAGE);
      return;
    }
    setBranchError(undefined);
    setCsvError(undefined);
    setCsvBusy(true);
    try {
      await downloadFile(
        "/api/stops-csv/download",
        { ...stopConfig, branch: trimmed },
        "stops.csv",
      );
    } catch (error) {
      setCsvError((error as Error).message || "Could not download stops CSV.");
    } finally {
      setCsvBusy(false);
    }
  }, [branch, stopConfig]);

  return (
    <section aria-labelledby="wizard-step-heading">
      <h2 id="wizard-step-heading" tabIndex={-1}>
        Your dataset is ready
      </h2>
      <p className="step-intro">
        Download the files below, then place <code>DRProject.config</code> in your DirectRoute
        user data directory (File → Preferences) and import the truck and stop files to build your
        solution. Optionally download a stops CSV with Branch and Action columns for OIS-style
        import testing.
      </p>

      <dl className="summary">
        <div className="summary-row">
          <dt>Territories (trucks)</dt>
          <dd>{truck.territory_count}</dd>
        </div>
        <div className="summary-row">
          <dt>Depots</dt>
          <dd>{truck.depot_count}</dd>
        </div>
        <div className="summary-row">
          <dt>Stops generated</dt>
          <dd>{stop.selected_stop_count}</dd>
        </div>
        <div className="summary-row">
          <dt>Output rows</dt>
          <dd>{stop.output_row_count}</dd>
        </div>
      </dl>

      <div className="download-buttons">
        <button
          type="button"
          className="primary"
          onClick={() => downloadBase64(truck.truck_file_base64, truck.filename, TRUCK_MIME)}
        >
          Download truck file ({truck.filename})
        </button>
        <button
          type="button"
          className="primary"
          onClick={() => downloadBase64(stop.stop_file_base64, stop.filename, STOP_MIME)}
        >
          Download stop file ({stop.filename})
        </button>
        <button
          type="button"
          className="primary"
          onClick={() =>
            downloadBase64(
              drprojectConfig.drproject_config_file_base64,
              drprojectConfig.filename,
              DRPROJECT_CONFIG_MIME,
            )
          }
        >
          Download project config ({drprojectConfig.filename})
        </button>
        <button type="button" className="primary" onClick={handleDownloadAll}>
          Download All ({DATASET_ZIP_FILENAME})
        </button>
      </div>
      {zipError ? (
        <p className="field-error" role="alert">
          {zipError}
        </p>
      ) : null}

      <div className="csv-download">
        <FormRow
          label="Branch name"
          htmlFor="stops-csv-branch"
          error={branchError}
          hint="Required to download the stops CSV. Applied as the Branch column on every row."
        >
          <input
            id="stops-csv-branch"
            type="text"
            value={branch}
            onChange={(event) => {
              setBranch(event.target.value);
              if (branchError) setBranchError(undefined);
            }}
            aria-invalid={branchError ? "true" : undefined}
            aria-describedby={
              [branchError ? "stops-csv-branch-error" : null, "stops-csv-branch-hint"]
                .filter(Boolean)
                .join(" ") || undefined
            }
            autoComplete="off"
          />
        </FormRow>
        {csvError ? (
          <p className="field-error" role="alert">
            {csvError}
          </p>
        ) : null}
        <button
          type="button"
          className="secondary"
          onClick={() => void handleCsvDownload()}
          disabled={csvBusy}
        >
          {csvBusy ? "Preparing CSV…" : "Download stops CSV (stops.csv)"}
        </button>
      </div>

      <div className="wizard-actions">
        <button type="button" className="secondary" onClick={onReset}>
          Start a new dataset
        </button>
      </div>
    </section>
  );
}
