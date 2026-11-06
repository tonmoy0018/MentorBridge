import Link from "next/link";
import { cn } from "@/lib/utils";

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className={cn("size-8", className)}>
      <rect width="32" height="32" rx="8" className="fill-primary" />
      <path
        d="M6 21c3.2-6.5 6.6-9.5 10-9.5s6.8 3 10 9.5"
        fill="none"
        strokeWidth="2.5"
        strokeLinecap="round"
        className="stroke-primary-foreground"
      />
      <path d="M11 21v-4.5M16 21v-6.5M21 21v-4.5" strokeWidth="2" strokeLinecap="round" className="stroke-primary-foreground/70" />
    </svg>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <Link href="/" className={cn("flex items-center gap-2 rounded-md font-semibold tracking-tight", className)}>
      <LogoMark />
      <span className="text-lg">MentorBridge</span>
    </Link>
  );
}
