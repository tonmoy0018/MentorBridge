import type { ReactNode } from "react";
import Link from "next/link";
import { Logo } from "@/components/layout/logo";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <header className="container-page flex h-16 items-center justify-between">
        <Logo />
        <Link href="/mentors" className="text-sm font-medium text-muted-foreground hover:text-foreground">
          Browse mentors
        </Link>
      </header>
      <main id="main" className="flex flex-1 items-start justify-center bg-muted/30 px-4 py-10 sm:py-16">
        <div className="w-full max-w-md">{children}</div>
      </main>
    </>
  );
}
