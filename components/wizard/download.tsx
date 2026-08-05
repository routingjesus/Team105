"use client";

import { downloadBase64, DRPROJECT_CONFIG_MIME, STOP_MIME, TRUCK_MIME } from "@/lib/api";
import type {
  DrprojectConfigResponse,
  StopGenerationResponse,
  TruckGenerationResponse,
} from "@/lib/wizard-types";

interface DownloadProps {
  truck: TruckGenerationResponse;
  stop: StopGenerationResponse;
  drprojectConfig: DrprojectConfigResponse;
  onReset: () => void;
}

export function Download({ truck, stop, drprojectConfig, onReset }: DownloadProps) {
  return (
    <section aria-labelledby="wizard-step-heading">
      <h2 id="wizard-step-heading" tabIndex={-1}>
        Your dataset is ready
      </h2>
      <p className="step-intro">
        Download all three files below, then place <code>DRProject.config</code> in your
        DirectRoute user data directory (File → Preferences) and import the truck and stop
        files to build your solution.
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
      </div>

      <div className="wizard-actions">
        <button type="button" className="secondary" onClick={onReset}>
          Start a new dataset
        </button>
      </div>
    </section>
  );
}
