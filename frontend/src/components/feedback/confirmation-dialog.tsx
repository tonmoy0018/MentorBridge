"use client";

import { useId, useState, type ReactNode } from "react";
import { getErrorMessage } from "@/lib/api/errors";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

interface ConfirmationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  destructive?: boolean;
  /** Show a reason textarea. `required` blocks confirmation until it has text. */
  reason?: { label: string; placeholder?: string; required?: boolean };
  /** Extra content between the description and the buttons. */
  children?: ReactNode;
  /** Throwing keeps the dialog open and shows the error inline. */
  onConfirm: (reason: string) => Promise<void> | void;
}

export function ConfirmationDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  cancelLabel = "Cancel",
  destructive,
  reason,
  children,
  onConfirm,
}: ConfirmationDialogProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reasonText, setReasonText] = useState("");
  const reasonId = useId();
  const errorId = useId();

  const reasonMissing = Boolean(reason?.required && !reasonText.trim());

  function handleOpenChange(next: boolean) {
    if (pending) return;
    if (!next) {
      setError(null);
      setReasonText("");
    }
    onOpenChange(next);
  }

  async function confirm() {
    if (reasonMissing) return;
    setPending(true);
    setError(null);
    try {
      await onConfirm(reasonText.trim());
      setReasonText("");
      onOpenChange(false);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setPending(false);
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          {description ? <AlertDialogDescription>{description}</AlertDialogDescription> : null}
        </AlertDialogHeader>
        {children}
        {reason ? (
          <div className="grid gap-2">
            <Label htmlFor={reasonId}>
              {reason.label}
              {reason.required ? null : (
                <span className="font-normal text-muted-foreground">(optional)</span>
              )}
            </Label>
            <Textarea
              id={reasonId}
              value={reasonText}
              onChange={(e) => setReasonText(e.target.value)}
              placeholder={reason.placeholder}
              maxLength={1000}
              required={reason.required}
              aria-describedby={error ? errorId : undefined}
            />
          </div>
        ) : null}
        {error ? (
          <p id={errorId} role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>{cancelLabel}</AlertDialogCancel>
          {/* A plain Button (not AlertDialogAction) so the dialog stays open while pending. */}
          <Button
            variant={destructive ? "destructive" : "default"}
            onClick={confirm}
            disabled={pending || reasonMissing}
            aria-busy={pending}
          >
            {pending ? "Working…" : confirmLabel}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
