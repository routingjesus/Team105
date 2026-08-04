"use client";

import { downloadBase64, STOP_MIME, TRUCK_MIME } from "@/lib/api";
import type { StopGenerationResponse, TruckGenerationResponse } from "@/lib/wizard-types";

interface DownloadProps {
  truck: TruckGenerationResponse;
  stop: StopGenerationResponse;
  onReset: () => void;
}

export function Download({ truck, stop, onReset }: DownloadProps) {
  return (
    <section aria-labelledby="wizard-step-heading">
      <h2 id="wizard-step-heading" tabIndex={-1}>
        Your dataset is ready
      </h2>
      <p className="step-intro">
        Download both files below, then import them into DirectRoute to build your solution.
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
      </div>

      <div className="wizard-actions">
        <button type="button" className="secondary" onClick={onReset}>
          Start a new dataset
        </button>
      </div>
    </section>
  );
}
