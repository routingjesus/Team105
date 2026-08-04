"use client";

import type { ReactNode } from "react";
import { useFormContext, type FieldPath } from "react-hook-form";
import type { WizardFormValues } from "@/lib/wizard-schema";

/** Convert an RHF field path into a DOM-id-safe string. */
export const idFrom = (name: string): string => name.replace(/[.[\]]+/g, "-").replace(/-$/, "");

interface FormRowProps {
  label: string;
  htmlFor: string;
  error?: string;
  hint?: string;
  children: ReactNode;
}

export function FormRow({ label, htmlFor, error, hint, children }: FormRowProps) {
  const hintId = hint ? `${htmlFor}-hint` : undefined;
  const errorId = error ? `${htmlFor}-error` : undefined;
  return (
    <div className="field" data-invalid={error ? "true" : undefined}>
      <label htmlFor={htmlFor}>{label}</label>
      {hint ? (
        <p className="field-hint" id={hintId}>
          {hint}
        </p>
      ) : null}
      {children}
      {error ? (
        <p className="field-error" role="alert" id={errorId}>
          {error}
        </p>
      ) : null}
    </div>
  );
}

interface TextFieldProps {
  name: FieldPath<WizardFormValues>;
  label: string;
  hint?: string;
  placeholder?: string;
  autoComplete?: string;
}

export function TextField({ name, label, hint, placeholder, autoComplete }: TextFieldProps) {
  const { register, getFieldState, formState } = useFormContext<WizardFormValues>();
  const { error } = getFieldState(name, formState);
  const id = idFrom(name);
  const describedBy =
    [error ? `${id}-error` : null, hint ? `${id}-hint` : null].filter(Boolean).join(" ") ||
    undefined;
  return (
    <FormRow label={label} htmlFor={id} error={error?.message} hint={hint}>
      <input
        id={id}
        type="text"
        placeholder={placeholder}
        autoComplete={autoComplete}
        aria-invalid={error ? "true" : undefined}
        aria-describedby={describedBy}
        {...register(name)}
      />
    </FormRow>
  );
}

interface NumberFieldProps {
  name: FieldPath<WizardFormValues>;
  label: string;
  hint?: string;
  min?: number;
  max?: number;
  step?: number | "any";
  placeholder?: string;
}

export function NumberField({ name, label, hint, min, max, step, placeholder }: NumberFieldProps) {
  const { register, getFieldState, formState } = useFormContext<WizardFormValues>();
  const { error } = getFieldState(name, formState);
  const id = idFrom(name);
  const describedBy =
    [error ? `${id}-error` : null, hint ? `${id}-hint` : null].filter(Boolean).join(" ") ||
    undefined;
  return (
    <FormRow label={label} htmlFor={id} error={error?.message} hint={hint}>
      <input
        id={id}
        type="number"
        inputMode="decimal"
        min={min}
        max={max}
        step={step}
        placeholder={placeholder}
        aria-invalid={error ? "true" : undefined}
        aria-describedby={describedBy}
        {...register(name, { valueAsNumber: true })}
      />
    </FormRow>
  );
}
