"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { api } from "@/lib/data/client";
import { applyServerErrors } from "@/lib/forms";
import { changePasswordSchema, type ChangePasswordValues } from "@/lib/validation/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/common/page-header";
import { useCurrentUser } from "@/components/dashboard/current-user";
import { FormAlert } from "@/components/forms/form-alert";
import { FormField } from "@/components/forms/form-field";
import { NativeSelect } from "@/components/forms/native-select";
import { PasswordInput } from "@/components/forms/password-input";
import { useApiErrorHandler } from "@/hooks/use-api-error-handler";

const accountSchema = z.object({
  first_name: z.string().trim().min(1, { error: "Enter your first name." }).max(80),
  last_name: z.string().trim().min(1, { error: "Enter your last name." }).max(80),
  timezone: z.string().min(1, { error: "Choose a time zone." }),
});
type AccountValues = z.infer<typeof accountSchema>;

export function useTimeZones(current: string) {
  return useMemo(() => {
    const zones = typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : [];
    return zones.includes(current) ? zones : [current, ...zones];
  }, [current]);
}

function AccountForm() {
  const { user, setUser } = useCurrentUser();
  const zones = useTimeZones(user.timezone);
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<AccountValues>({
    resolver: zodResolver(accountSchema),
    defaultValues: { first_name: user.first_name, last_name: user.last_name, timezone: user.timezone },
  });

  async function onSubmit(values: AccountValues) {
    setFormError(null);
    try {
      const updated = await api.account.update(values);
      setUser(updated);
      reset(values);
      toast.success("Account details saved");
    } catch (error) {
      setFormError(applyServerErrors(error, setError, ["first_name", "last_name", "timezone"]));
    }
  }

  return (
    <section aria-labelledby="account-heading" className="rounded-xl border bg-card p-6">
      <h2 id="account-heading" className="text-lg font-semibold">
        Account details
      </h2>
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="mt-5 grid gap-5">
        {formError ? <FormAlert>{formError}</FormAlert> : null}
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <FormField label="First name" error={errors.first_name?.message} required>
            {(props) => <Input {...props} autoComplete="given-name" {...register("first_name")} />}
          </FormField>
          <FormField label="Last name" error={errors.last_name?.message} required>
            {(props) => <Input {...props} autoComplete="family-name" {...register("last_name")} />}
          </FormField>
        </div>
        <FormField label="Email" description="Contact support to change the email on your account.">
          {(props) => <Input {...props} type="email" value={user.email} readOnly disabled />}
        </FormField>
        <EmailVerificationStatus verified={user.email_verified} />
        <FormField
          label="Time zone"
          error={errors.timezone?.message}
          description="Session times across MentorBridge are shown in this time zone."
          required
        >
          {(props) => (
            <NativeSelect {...props} {...register("timezone")}>
              {zones.map((zone) => (
                <option key={zone} value={zone}>
                  {zone.replace(/_/g, " ")}
                </option>
              ))}
            </NativeSelect>
          )}
        </FormField>
        <div>
          <Button type="submit" disabled={isSubmitting || !isDirty}>
            {isSubmitting ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </form>
    </section>
  );
}

function EmailVerificationStatus({ verified }: { verified: boolean }) {
  const [state, setState] = useState<"idle" | "pending" | "sent">("idle");
  const handleError = useApiErrorHandler();
  if (verified) return <p className="-mt-2 text-sm text-success">Your email address is verified.</p>;
  return (
    <div className="-mt-2 flex flex-wrap items-center gap-3 text-sm">
      <span className="text-warning">Your email address isn&apos;t verified yet.</span>
      {state === "sent" ? (
        <span className="text-muted-foreground">Check your inbox for a new link.</span>
      ) : (
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={state === "pending"}
          onClick={async () => {
            setState("pending");
            try {
              await api.auth.resendVerificationEmail();
              setState("sent");
            } catch (error) {
              setState("idle");
              handleError(error, "Couldn't send the email");
            }
          }}
        >
          {state === "pending" ? "Sending…" : "Resend verification email"}
        </Button>
      )}
    </div>
  );
}

function PasswordForm() {
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ChangePasswordValues>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: { current_password: "", new_password: "", confirm_password: "" },
  });

  async function onSubmit(values: ChangePasswordValues) {
    setFormError(null);
    try {
      await api.auth.changePassword({ current_password: values.current_password, new_password: values.new_password });
      reset();
      toast.success("Password changed");
    } catch (error) {
      setFormError(applyServerErrors(error, setError, ["current_password", "new_password"]));
    }
  }

  return (
    <section aria-labelledby="password-heading" className="rounded-xl border bg-card p-6">
      <h2 id="password-heading" className="text-lg font-semibold">
        Change password
      </h2>
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="mt-5 grid max-w-md gap-5">
        {formError ? <FormAlert>{formError}</FormAlert> : null}
        <FormField label="Current password" error={errors.current_password?.message} required>
          {(props) => <PasswordInput {...props} autoComplete="current-password" {...register("current_password")} />}
        </FormField>
        <FormField
          label="New password"
          error={errors.new_password?.message}
          description="At least 8 characters."
          required
        >
          {(props) => <PasswordInput {...props} autoComplete="new-password" {...register("new_password")} />}
        </FormField>
        <FormField label="Confirm new password" error={errors.confirm_password?.message} required>
          {(props) => <PasswordInput {...props} autoComplete="new-password" {...register("confirm_password")} />}
        </FormField>
        <div>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Updating…" : "Update password"}
          </Button>
        </div>
      </form>
    </section>
  );
}

export function AccountSettings() {
  return (
    <div className="grid grid-cols-1 gap-6">
      <PageHeader title="Settings" description="Manage your account details and password." />
      <AccountForm />
      <PasswordForm />
    </div>
  );
}
