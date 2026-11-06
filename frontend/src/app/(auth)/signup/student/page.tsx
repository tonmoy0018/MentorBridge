import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { AuthCard } from "@/components/auth/auth-card";
import { RedirectIfSignedIn } from "@/components/auth/redirect-if-signed-in";
import { SignupForm } from "@/components/auth/signup-form";

export const metadata: Metadata = { title: "Create a student account" };

export default function StudentSignupPage() {
  return (
    <>
      <Suspense fallback={null}>
        <RedirectIfSignedIn />
      </Suspense>
      <AuthCard
        title="Create your student account"
        description="Find mentors, book sessions and track your career goals."
        footer={
          <>
            Want to mentor instead?{" "}
            <Link href="/signup/mentor" className="font-medium text-primary hover:underline">
              Sign up as a mentor
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
        <SignupForm role="student" />
      </AuthCard>
    </>
  );
}
