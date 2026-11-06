import { BadgeCheck } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Rendered only when the backend reports the mentor as verified (approved through the
 * admin verification workflow). Never pass a hard-coded `true`.
 */
export function VerifiedBadge({
  verified,
  compact,
  className,
}: {
  verified: boolean;
  compact?: boolean;
  className?: string;
}) {
  if (!verified) return null;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground",
        compact && "bg-transparent p-0",
        className,
      )}
      title="Profile reviewed and approved by MentorBridge"
    >
      <BadgeCheck className="size-4 text-primary" aria-hidden="true" />
      <span className={cn(compact && "sr-only")}>Verified</span>
    </span>
  );
}
