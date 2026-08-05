"use client";

import { useCallback, useEffect, useState } from "react";
import { FormProvider, useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  defaultWizardValues,
  stopStepFields,
  truckStepFields,
  wizardSchema,
  type WizardFormValues,
} from "@/lib/wizard-schema";
import { ApiError, generateDrprojectConfig, generateStops, generateTruck, stepForFormPath } from "@/lib/api";
import { buildStopConfig, buildTruckConfig } from "@/lib/build-config";
import type {
  DrprojectConfigResponse,
  StopConfig,
  StopGenerationResponse,
  TruckGenerationResponse,
} from "@/lib/wizard-types";
import {
  clearPersistedValues,
  loadPersistedValues,
  persistValues,
} from "@/hooks/use-wizard-persistence";
import { StepIndicator } from "./step-indicator";
import { TruckQuestions } from "./truck-questions";
import { StopQuestions } from "./stop-questions";
import { Review } from "./review";
import { Download } from "./download";

const STEPS = ["Route details", "Stop details", "Review", "Download"];

interface GenerationResult {
  truck: TruckGenerationResponse;
  stop: StopGenerationResponse;
  drprojectConfig: DrprojectConfigResponse;
  stopConfig: StopConfig;
}

/** Earliest wizard step (0 = route, 1 = stop) that owns any of the given field paths. */
function firstOwnerStep(paths: string[]): number | null {
  const owners = paths.map(stepForFormPath).filter((s): s is 0 | 1 => s !== null);
  return owners.length > 0 ? Math.min(...owners) : null;
}

export function DatasetWizard() {
  const methods = useForm<WizardFormValues>({
    resolver: zodResolver(wizardSchema) as unknown as Resolver<WizardFormValues>,
    defaultValues: defaultWizardValues,
    mode: "onTouched",
    shouldUnregister: false,
    shouldFocusError: true,
  });

  const [step, setStep] = useState(0);
  const [furthest, setFurthest] = useState(0);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<GenerationResult | null>(null);

  // Rehydrate persisted answers after mount to avoid SSR/client mismatch.
  useEffect(() => {
    const persisted = loadPersistedValues();
    if (persisted) methods.reset({ ...defaultWizardValues, ...persisted });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Persist answers on every change so a mid-flow refresh keeps them.
  useEffect(() => {
    const sub = methods.watch((values) => persistValues(values as WizardFormValues));
    return () => sub.unsubscribe();
  }, [methods]);

  // Move focus to the step heading on each transition (a11y).
  useEffect(() => {
    document.getElementById("wizard-step-heading")?.focus();
  }, [step, result]);

  // Browser Back decrements the step (demo hardening).
  useEffect(() => {
    if (typeof window === "undefined") return;
    const onPop = () => setStep((s) => Math.max(0, s - 1));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const goToStep = useCallback((next: number) => {
    setStep(next);
    setFurthest((f) => Math.max(f, next));
  }, []);

  const advance = useCallback(
    (next: number) => {
      if (typeof window !== "undefined") {
        window.history.pushState({ wizardStep: next }, "");
      }
      goToStep(next);
    },
    [goToStep],
  );

  const clearRoot = useCallback(() => methods.clearErrors("root"), [methods]);

  const handleNext = useCallback(async () => {
    clearRoot();
    const fields = step === 0 ? truckStepFields : stopStepFields;
    const valid = await methods.trigger(
      fields as unknown as Parameters<typeof methods.trigger>[0],
    );
    if (valid) advance(step + 1);
  }, [advance, clearRoot, methods, step]);

  const handleBack = useCallback(() => {
    clearRoot();
    setStep((s) => Math.max(0, s - 1));
  }, [clearRoot]);

  const applyApiError = useCallback(
    (error: ApiError) => {
      error.fieldErrors.forEach((fe) => {
        methods.setError(fe.path as Parameters<typeof methods.setError>[0], {
          type: "server",
          message: fe.message,
        });
      });
      if (error.rootMessage) {
        methods.setError("root.serverError", { type: "server", message: error.rootMessage });
      }
      const owner = firstOwnerStep(error.fieldErrors.map((fe) => fe.path));
      if (owner !== null) setStep(owner);
    },
    [methods],
  );

  const runGeneration = methods.handleSubmit(
    async (values) => {
      setGenerating(true);
      methods.clearErrors("root");
      try {
        const truck = await generateTruck(buildTruckConfig(values));
        const stopConfig = buildStopConfig(values, truck);
        const stop = await generateStops(stopConfig);
        const drprojectConfig = await generateDrprojectConfig(stopConfig);
        setResult({ truck, stop, drprojectConfig, stopConfig });
        clearPersistedValues();
        advance(3);
      } catch (error) {
        if (error instanceof ApiError) {
          applyApiError(error);
        } else {
          methods.setError("root.serverError", {
            type: "server",
            message: (error as Error).message,
          });
        }
      } finally {
        setGenerating(false);
      }
    },
    (errors) => {
      const owner = firstOwnerStep(Object.keys(errors));
      if (owner !== null) setStep(owner);
    },
  );

  const handleReset = useCallback(() => {
    methods.reset(defaultWizardValues);
    clearPersistedValues();
    setResult(null);
    setStep(0);
    setFurthest(0);
  }, [methods]);

  const rootError = methods.formState.errors.root?.serverError?.message as string | undefined;

  return (
    <FormProvider {...methods}>
      <div className="wizard">
        <StepIndicator steps={STEPS} current={step} furthest={furthest} onSelect={goToStep} />
        <form onSubmit={(e) => e.preventDefault()} noValidate>
          {rootError && step !== 2 ? (
            <div className="alert" role="alert">
              {rootError}
            </div>
          ) : null}

          {step === 0 ? <TruckQuestions /> : null}
          {step === 1 ? <StopQuestions /> : null}
          {step === 2 ? (
            <Review
              onNavigate={goToStep}
              onGenerate={runGeneration}
              generating={generating}
              rootError={rootError}
            />
          ) : null}
          {step === 3 && result ? (
            <Download
              truck={result.truck}
              stop={result.stop}
              drprojectConfig={result.drprojectConfig}
              stopConfig={result.stopConfig}
              onReset={handleReset}
            />
          ) : null}

          {step < 2 ? (
            <div className="wizard-actions">
              {step > 0 ? (
                <button type="button" className="secondary" onClick={handleBack}>
                  Back
                </button>
              ) : (
                <span />
              )}
              <button type="button" className="primary" onClick={handleNext}>
                Continue
              </button>
            </div>
          ) : null}
        </form>
      </div>
    </FormProvider>
  );
}
