"use client";

import { useFormContext } from "react-hook-form";
import { FREQUENCY_LABELS } from "@/lib/wizard-types";
import { parseStates, type WizardFormValues } from "@/lib/wizard-schema";

interface ReviewProps {
  onNavigate: (step: number) => void;
  onGenerate: () => void;
  generating: boolean;
  rootError?: string;
}

interface RowProps {
  label: string;
  value: string;
  onChange: () => void;
  changeLabel: string;
}

function SummaryRow({ label, value, onChange, changeLabel }: RowProps) {
  return (
    <div className="summary-row">
      <dt>{label}</dt>
      <dd>{value}</dd>
      <button type="button" className="link-button" onClick={onChange}>
        Change<span className="sr-only"> {changeLabel}</span>
      </button>
    </div>
  );
}

export function Review({ onNavigate, onGenerate, generating, rootError }: ReviewProps) {
  const { getValues } = useFormContext<WizardFormValues>();
  const v = getValues();

  const totalTrucks = v.depots.reduce((sum, d) => sum + (Number(d.trucks) || 0), 0);
  const volumeNames = v.volumes.map((vol) => vol.name).filter(Boolean).join(", ") || "—";
  const selectionText =
    v.selectionMode === "radius"
      ? `Within ${v.radiusMiles ?? "?"} miles of depots`
      : `States: ${parseStates(v.states).join(", ") || "—"}`;
  const frequencyText =
    (v.frequencyValues ?? [])
      .map((f) => FREQUENCY_LABELS[String(f)] ?? String(f))
      .join(", ") || "—";
  const windowText =
    v.timeWindowMode === "fixed"
      ? `Fixed ${v.open1 ?? "?"}–${v.close1 ?? "?"}`
      : "Randomized windows";

  return (
    <section aria-labelledby="wizard-step-heading">
      <h2 id="wizard-step-heading" tabIndex={-1}>
        Check your answers
      </h2>
      <p className="step-intro">
        Review the dataset you&apos;re about to generate. You can change any answer before
        generating.
      </p>

      {rootError ? (
        <div className="alert" role="alert">
          <strong>Generation failed.</strong> {rootError}
        </div>
      ) : null}

      <h3 className="summary-heading">Route details</h3>
      <dl className="summary">
        <SummaryRow
          label="Depots"
          value={String(v.depots.length)}
          onChange={() => onNavigate(0)}
          changeLabel="number of depots"
        />
        <SummaryRow
          label="Total trucks"
          value={String(totalTrucks)}
          onChange={() => onNavigate(0)}
          changeLabel="trucks per depot"
        />
        <SummaryRow
          label="Planning weeks"
          value={String(v.weeks)}
          onChange={() => onNavigate(0)}
          changeLabel="planning weeks"
        />
        <SummaryRow
          label="Volumes"
          value={volumeNames}
          onChange={() => onNavigate(0)}
          changeLabel="volumes"
        />
      </dl>

      <h3 className="summary-heading">Stop details</h3>
      <dl className="summary">
        <SummaryRow
          label="Number of stops"
          value={String(v.stopCount)}
          onChange={() => onNavigate(1)}
          changeLabel="number of stops"
        />
        <SummaryRow
          label="Stop sourcing"
          value={selectionText}
          onChange={() => onNavigate(1)}
          changeLabel="stop sourcing"
        />
        <SummaryRow
          label="Service frequency"
          value={frequencyText}
          onChange={() => onNavigate(1)}
          changeLabel="service frequency"
        />
        <SummaryRow
          label="Delivery windows"
          value={windowText}
          onChange={() => onNavigate(1)}
          changeLabel="delivery windows"
        />
      </dl>

      <div className="wizard-actions">
        <button type="button" className="secondary" onClick={() => onNavigate(1)}>
          Back
        </button>
        <button type="button" className="primary" onClick={onGenerate} disabled={generating}>
          {generating ? "Generating…" : "Generate dataset"}
        </button>
      </div>
      <p className="assertive" role="status" aria-live="polite">
        {generating ? "Generating your dataset. This can take a few seconds." : ""}
      </p>
    </section>
  );
}
