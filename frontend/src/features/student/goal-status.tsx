import type { GoalStatus } from "@/lib/api/types";
import { StatusBadge, type Tone } from "@/components/common/status-badge";

export const GOAL_STATUS: Record<GoalStatus, { label: string; tone: Tone }> = {
  not_started: { label: "Not started", tone: "neutral" },
  in_progress: { label: "In progress", tone: "info" },
  achieved: { label: "Achieved", tone: "success" },
  archived: { label: "Archived", tone: "neutral" },
};

export function GoalStatusBadge({ status }: { status: GoalStatus }) {
  return <StatusBadge tone={GOAL_STATUS[status].tone}>{GOAL_STATUS[status].label}</StatusBadge>;
}
