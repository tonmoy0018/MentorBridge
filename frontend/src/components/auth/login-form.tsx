"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { isApiError } from "@/lib/api/errors";
import { api } from "@/lib/data/client";
import { applyServerErrors } from "@/lib/forms";
import { dashboardPathFor, safeNextPath } from "@/lib/routes";
import { loginSchema, type LoginValues } from "@/lib/validation/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FormAlert } from "@/components/forms/form-alert";
import { FormField } from "@/components/forms/form-field";
import { PasswordInput } from "@/components/forms/password-input";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [formError, setFormError] = useState<string | null>(null);
  const sessionExpired = searchParams.get("reason") === "expired";
  const passwordReset = searchParams.get("reset") === "1";

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  async function onSubmit(values: LoginValues) {
    setFormError(null);
    try {
      const user = await api.auth.login(values);
      router.replace(safeNextPath(searchParams.get("next"), dashboardPathFor(user.role)));
      router.refresh();
    } catch (error) {
      if (isApiError(error) && (error.code === "invalid_credentials" || error.kind === "validation")) {
        // Same message whether the email exists or not (no account enumeration).
        setFormError(applyServerErrors(error, setError, ["email", "password"]) ?? "Email or password is incorrect.");
        return;
      }
      setFormError(applyServerErrors(error, setError, []));
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid gap-5">
      {sessionExpired ? <FormAlert title="Session ended">Please log in again to continue.</FormAlert> : null}
      {passwordReset ? (
        <FormAlert variant="success">Your password has been reset. Log in with your new password.</FormAlert>
      ) : null}
      {formError ? <FormAlert>{formError}</FormAlert> : null}

      <FormField label="Email" error={errors.email?.message} required>
        {(props) => <Input {...props} type="email" autoComplete="email" {...register("email")} />}
      </FormField>

      <FormField label="Password" error={errors.password?.message} required>
        {(props) => <PasswordInput {...props} autoComplete="current-password" {...register("password")} />}
      </FormField>

      <div className="-mt-2 text-right">
        <Link href="/forgot-password" className="text-sm font-medium text-primary hover:underline">
          Forgot your password?
        </Link>
      </div>

      <Button type="submit" size="lg" disabled={isSubmitting}>
        {isSubmitting ? "Logging in…" : "Log in"}
      </Button>
    </form>
  );
}
