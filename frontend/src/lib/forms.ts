import type { FieldValues, Path, UseFormSetError } from "react-hook-form";
import { getErrorMessage, isApiError } from "@/lib/api/errors";

/**
 * Copies server-side field errors (DRF `details.fields`) onto react-hook-form fields.
 * Returns the message to show at form level for errors that don't belong to a field,
 * or null when every error was attached to a field.
 */
export function applyServerErrors<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  fields: readonly Path<T>[],
): string | null {
  if (!isApiError(error)) return getErrorMessage(error);

  const known = new Set<string>(fields);
  const unmatched: string[] = [];
  let matched = false;
  for (const [field, messages] of Object.entries(error.fieldErrors)) {
    if (known.has(field)) {
      setError(field as Path<T>, { type: "server", message: messages.join(" ") });
      matched = true;
    } else {
      unmatched.push(...messages);
    }
  }
  if (unmatched.length > 0) return unmatched.join(" ");
  return matched ? null : error.message;
}
