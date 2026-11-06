import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { AuthCard } from "@/components/auth/auth-card";
import { RedirectIfSignedIn } from "@/components/auth/redirect-if-signed-in";
import { FormSkeleton } from "@/components/auth/form-skeleton";
import { LoginForm } from "@/components/auth/login-form";

export const metadata: Metadata = { title: "Log in" };

export default function LoginPage() {
  return (
    <>
      <Suspense fallback={null}>
        <RedirectIfSignedIn />
      </Suspense>
      <AuthCard
        title="Welcome back"
        description="Log in to manage your sessions and bookings."
        footer={
          <>
            New to MentorBridge?{" "}
            <Link href="/signup" className="font-medium text-primary hover:underline">
              Create an account
            </Link>
          </>
        }
      >
        {/* Reads ?next= and ?reason= from the URL, so it renders at request time. */}
        <Suspense fallback={<FormSkeleton />}>
          <LoginForm />
        </Suspense>
      </AuthCard>
    </>
  );
}
