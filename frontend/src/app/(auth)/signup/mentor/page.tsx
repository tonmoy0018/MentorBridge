import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { AuthCard } from "@/components/auth/auth-card";
import { RedirectIfSignedIn } from "@/components/auth/redirect-if-signed-in";
import { SignupForm } from "@/components/auth/signup-form";

export const metadata: Metadata = { title: "Become a mentor" };

export default function MentorSignupPage() {
  return (
    <>
      <Suspense fallback={null}>
        <RedirectIfSignedIn />
      </Suspense>
      <AuthCard
        title="Become a mentor"
        description={
          <>
            Create your account, then complete your profile and submit it for review. Your profile becomes visible
            to students once our team has approved it.
          </>
        }
        footer={
          <>
            Looking for a mentor?{" "}
            <Link href="/signup/student" className="font-medium text-primary hover:underline">
              Sign up as a student
            </Link>
            <span className="mx-2" aria-hidden="true">
              ·
            </span>
            <Link href="/login" className="font-medium text-primary hover:underline">
              Log in
            </Link>
          </>
        }
      >
        <SignupForm role="mentor" />
      </AuthCard>
    </>
  );
}
