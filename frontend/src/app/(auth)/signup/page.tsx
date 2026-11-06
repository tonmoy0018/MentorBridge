import { ArrowRight, GraduationCap, Presentation } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { AuthCard } from "@/components/auth/auth-card";
import { RedirectIfSignedIn } from "@/components/auth/redirect-if-signed-in";

export const metadata: Metadata = { title: "Sign up" };

const PATHS = [
  {
    href: "/signup/student",
    icon: GraduationCap,
    title: "I'm looking for a mentor",
    text: "Students and early-career professionals who want one-to-one guidance.",
  },
  {
    href: "/signup/mentor",
    icon: Presentation,
    title: "I want to mentor",
    text: "Experienced professionals who want to share what they know.",
  },
];

export default function SignupChooserPage() {
  return (
    <>
      <Suspense fallback={null}>
        <RedirectIfSignedIn />
      </Suspense>
      <AuthCard
        title="Join MentorBridge"
        description="Choose how you'd like to use MentorBridge. You can't change this later, so pick the one that fits."
        footer={
          <>
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-primary hover:underline">
              Log in
            </Link>
          </>
        }
      >
        <ul className="grid gap-3">
          {PATHS.map((path) => (
            <li key={path.href}>
              <Link
                href={path.href}
                className="group flex items-center gap-4 rounded-xl border p-4 transition-colors hover:border-primary/50 hover:bg-accent/40"
              >
                <span className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">
                  <path.icon className="size-5" aria-hidden="true" />
                </span>
                <span className="flex-1">
                  <span className="block font-medium">{path.title}</span>
                  <span className="block text-sm text-muted-foreground">{path.text}</span>
                </span>
                <ArrowRight className="size-4 text-muted-foreground group-hover:text-primary" aria-hidden="true" />
              </Link>
            </li>
          ))}
        </ul>
      </AuthCard>
    </>
  );
}
