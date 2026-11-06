"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { isApiError } from "@/lib/api/errors";
import { api } from "@/lib/data/client";
import { applyServerErrors } from "@/lib/forms";
import { resetPasswordSchema, type ResetPasswordValues } from "@/lib/validation/auth";
import { Button } from "@/components/ui/button";
import { FormAlert } from "@/components/forms/form-alert";
import { FormField } from "@/components/forms/form-field";
import { PasswordInput } from "@/components/forms/password-input";

export function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const uid = searchParams.get("uid");
  const token = searchParams.get("token");
  const [formError, setFormError] = useState<string | null>(null);
  const [linkInvalid, setLinkInvalid] = useState(!uid || !token);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { new_password: "", confirm_password: "" },
  });

  if (linkInvalid || !uid || !token) {
    return (
      <div className="grid gap-5">
        <FormAlert title="This link is invalid or has expired">
          Password reset links can only be used once and expire after a short time.
        </FormAlert>
        <Button asChild size="lg">
          <Link href="/forgot-password">Request a new link</Link>
        </Button>
      </div>
    );
  }

  async function onSubmit(values: ResetPasswordValues) {
    setFormError(null);
    try {
      await api.auth.confirmPasswordReset({ uid: uid!, token: token!, new_password: values.new_password });
      router.replace("/login?reset=1");
    } catch (error) {
      if (isApiError(error) && (error.code === "invalid_token" || error.fieldErrors.token || error.fieldErrors.uid)) {
        setLinkInvalid(true);
        return;
      }
      setFormError(applyServerErrors(error, setError, ["new_password"]));
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid gap-5">
      {formError ? <FormAlert>{formError}</FormAlert> : null}
      <FormField
        label="New password"
        error={errors.new_password?.message}
        description="At least 8 characters. Avoid common words and personal details."
        required
      >
        {(props) => <PasswordInput {...props} autoComplete="new-password" {...register("new_password")} />}
      </FormField>
      <FormField label="Confirm new password" error={errors.confirm_password?.message} required>
        {(props) => <PasswordInput {...props} autoComplete="new-password" {...register("confirm_password")} />}
      </FormField>
      <Button type="submit" size="lg" disabled={isSubmitting}>
        {isSubmitting ? "Saving…" : "Set new password"}
      </Button>
    </form>
  );
}
