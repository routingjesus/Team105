"use client";

interface StepIndicatorProps {
  steps: string[];
  current: number;
  furthest: number;
  onSelect: (index: number) => void;
}

export function StepIndicator({ steps, current, furthest, onSelect }: StepIndicatorProps) {
  return (
    <nav className="step-indicator" aria-label="Progress">
      <p className="step-count">
        Step {current + 1} of {steps.length}
      </p>
      <ol>
        {steps.map((label, index) => {
          const state =
            index === current ? "current" : index < furthest || index < current ? "done" : "upcoming";
          const reachable = index <= furthest;
          return (
            <li key={label} data-state={state}>
              <button
                type="button"
                onClick={() => reachable && onSelect(index)}
                disabled={!reachable}
                aria-current={index === current ? "step" : undefined}
              >
                <span className="step-dot" aria-hidden="true">
                  {index + 1}
                </span>
                <span className="step-label">{label}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
