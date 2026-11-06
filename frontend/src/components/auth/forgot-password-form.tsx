"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { api } from "@/lib/data/client";
import { applyServerErrors } from "@/lib/forms";
import { forgotPasswordSchema, type ForgotPasswordValues } from "@/lib/validation/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FormAlert } from "@/components/forms/form-alert";
import { FormField } from "@/components/forms/form-field";

export function ForgotPasswordForm() {
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
  });

  async function onSubmit(values: ForgotPasswordValues) {
    setFormError(null);
    try {
      await api.auth.requestPasswordReset(values.email);
      setSentTo(values.email);
    } catch (error) {
      setFormError(applyServerErrors(error, setError, ["email"]));
    }
  }

  if (sentTo) {
    return (
      <FormAlert variant="success" title="Check your email">
        If an account exists for {sentTo}, we&apos;ve sent a link to reset your password. The link expires
        after a short time.
      </FormAlert>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid gap-5">
      {formError ? <FormAlert>{formError}</FormAlert> : null}
      <FormField label="Email" error={errors.email?.message} required>
        {(props) => <Input {...props} type="email" autoComplete="email" {...register("email")} />}
      </FormField>
      <Button type="submit" size="lg" disabled={isSubmitting}>
        {isSubmitting ? "Sending…" : "Send reset link"}
      </Button>
    </form>
  );
}
