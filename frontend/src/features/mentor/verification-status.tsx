import { BadgeCheck, Clock, FileWarning, PencilLine, ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";
import type { VerificationStatus } from "@/lib/api/types";
import { StatusBadge, type Tone } from "@/components/common/status-badge";

export const VERIFICATION: Record<
  VerificationStatus,
  { label: string; tone: Tone; icon: typeof BadgeCheck; message: string }
> = {
  draft: {
    label: "Not submitted",
    tone: "neutral",
    icon: PencilLine,
    message: "Complete your profile and submit it for review. Students can't see your profile until it's approved.",
  },
  pending: {
    label: "Under review",
    tone: "info",
    icon: Clock,
    message: "Our team is reviewing your profile. You'll get an email when there's a decision.",
  },
  approved: {
    label: "Approved",
    tone: "success",
    icon: BadgeCheck,
    message: "Your profile is verified and visible to students.",
  },
  rejected: {
    label: "Changes needed",
    tone: "danger",
    icon: FileWarning,
    message: "Your profile wasn't approved. Review the feedback, update your profile and submit it again.",
  },
  suspended: {
    label: "Suspended",
    tone: "danger",
    icon: ShieldAlert,
    message: "Your profile is hidden from students. Contact MentorBridge support for details.",
  },
};

export function VerificationBadge({ status }: { status: VerificationStatus }) {
  return <StatusBadge tone={VERIFICATION[status].tone}>{VERIFICATION[status].label}</StatusBadge>;
}

export function VerificationNotice({
  status,
  reason,
  action,
}: {
  status: VerificationStatus;
  reason?: string | null;
  action?: ReactNode;
}) {
  const info = VERIFICATION[status];
  return (
    <div className="flex flex-col gap-4 rounded-xl border bg-card p-5 sm:flex-row sm:items-center">
      <info.icon className="size-6 shrink-0 text-primary" aria-hidden="true" />
      <div className="flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-semibold">Profile verification</p>
          <VerificationBadge status={status} />
        </div>
        <p className="mt-1 text-sm text-muted-foreground">{info.message}</p>
        {status === "rejected" && reason ? (
          <p className="mt-2 text-sm">
            <span className="font-medium">Reviewer feedback:</span> {reason}
          </p>
        ) : null}
      </div>
      {action}
    </div>
  );
}
