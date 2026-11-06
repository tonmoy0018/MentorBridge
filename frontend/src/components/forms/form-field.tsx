import { useId, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Label } from "@/components/ui/label";

export interface FieldControlProps {
  id: string;
  "aria-invalid": boolean | undefined;
  "aria-describedby": string | undefined;
  "aria-required": boolean | undefined;
}

interface FormFieldProps {
  label: ReactNode;
  /** Validation message; when present the control is marked invalid. */
  error?: string;
  description?: ReactNode;
  required?: boolean;
  /** Visually hide the label (it is still read by screen readers). */
  hideLabel?: boolean;
  className?: string;
  /** Render the control, spreading the accessibility props onto it. */
  children: (props: FieldControlProps) => ReactNode;
  id?: string;
}

/**
 * Label + control + help text + error, wired together with ids so assistive technology
 * announces the label, the description and any error for the control.
 */
export function FormField({
  label,
  error,
  description,
  required,
  hideLabel,
  className,
  children,
  id: providedId,
}: FormFieldProps) {
  const generatedId = useId();
  const id = providedId ?? generatedId;
  const descriptionId = description ? `${id}-description` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [descriptionId, errorId].filter(Boolean).join(" ") || undefined;

  return (
    <div className={cn("grid gap-2", className)}>
      <Label htmlFor={id} className={cn(hideLabel && "sr-only")}>
        {label}
        {required ? (
          <span aria-hidden="true" className="text-destructive">
            *
          </span>
        ) : null}
      </Label>
      {children({
        id,
        "aria-invalid": error ? true : undefined,
        "aria-describedby": describedBy,
        "aria-required": required || undefined,
      })}
      {description ? (
        <p id={descriptionId} className="text-xs text-muted-foreground">
          {description}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** Fieldset + legend for groups of checkboxes or radios. */
export function FormFieldset({
  legend,
  description,
  error,
  children,
  className,
}: {
  legend: ReactNode;
  description?: ReactNode;
  error?: string;
  children: ReactNode;
  className?: string;
}) {
  const id = useId();
  return (
    <fieldset
      className={cn("grid gap-3", className)}
      aria-describedby={error ? `${id}-error` : undefined}
    >
      <legend className="mb-1 text-sm font-medium">{legend}</legend>
      {description ? <p className="-mt-2 text-xs text-muted-foreground">{description}</p> : null}
      {children}
      {error ? (
        <p id={`${id}-error`} className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </fieldset>
  );
}
