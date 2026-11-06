import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthCard } from "@/components/auth/auth-card";
import { FormSkeleton } from "@/components/auth/form-skeleton";
import { VerifyEmailForm } from "@/components/auth/verify-email-form";

export const metadata: Metadata = { title: "Confirm your email" };

export default function VerifyEmailPage() {
  return (
    <AuthCard title="Confirm your email" description="Confirm the email address for your MentorBridge account.">
      <Suspense fallback={<FormSkeleton fields={0} />}>
        <VerifyEmailForm />
      </Suspense>
    </AuthCard>
  );
}
