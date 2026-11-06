"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import type { RegisterInput } from "@/lib/api/types";
import { api } from "@/lib/data/client";
import { detectTimeZone } from "@/lib/format";
import { applyServerErrors } from "@/lib/forms";
import { signupSchema, type SignupValues } from "@/lib/validation/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FormAlert } from "@/components/forms/form-alert";
import { FormField } from "@/components/forms/form-field";
import { PasswordInput } from "@/components/forms/password-input";

const AFTER_SIGNUP: Record<RegisterInput["role"], string> = {
  student: "/dashboard/student",
  // New mentors land on their profile to complete it before submitting for verification.
  mentor: "/dashboard/mentor/profile",
};

export function SignupForm({ role }: { role: RegisterInput["role"] }) {
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<SignupValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: { first_name: "", last_name: "", email: "", password: "", confirm_password: "" },
  });

  async function onSubmit(values: SignupValues) {
    setFormError(null);
    try {
      await api.auth.register({
        email: values.email,
        password: values.password,
        first_name: values.first_name,
        last_name: values.last_name,
        role,
        timezone: detectTimeZone(),
      });
      router.replace(AFTER_SIGNUP[role]);
      router.refresh();
    } catch (error) {
      setFormError(applyServerErrors(error, setError, ["first_name", "last_name", "email", "password"]));
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid gap-5">
      {formError ? <FormAlert>{formError}</FormAlert> : null}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <FormField label="First name" error={errors.first_name?.message} required>
          {(props) => <Input {...props} autoComplete="given-name" {...register("first_name")} />}
        </FormField>
        <FormField label="Last name" error={errors.last_name?.message} required>
          {(props) => <Input {...props} autoComplete="family-name" {...register("last_name")} />}
        </FormField>
      </div>
      <FormField label="Email" error={errors.email?.message} required>
        {(props) => <Input {...props} type="email" autoComplete="email" {...register("email")} />}
      </FormField>
      <FormField
        label="Password"
        error={errors.password?.message}
        description="At least 8 characters. Avoid common words and personal details."
        required
      >
        {(props) => <PasswordInput {...props} autoComplete="new-password" {...register("password")} />}
      </FormField>
      <FormField label="Confirm password" error={errors.confirm_password?.message} required>
        {(props) => <PasswordInput {...props} autoComplete="new-password" {...register("confirm_password")} />}
      </FormField>
      <Button type="submit" size="lg" disabled={isSubmitting}>
        {isSubmitting ? "Creating account…" : role === "mentor" ? "Create mentor account" : "Create student account"}
      </Button>
    </form>
  );
}
