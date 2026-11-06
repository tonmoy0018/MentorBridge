"use client";

import { Heart } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { getErrorMessage, isApiError } from "@/lib/api/errors";
import { api } from "@/lib/data/client";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { loginRedirectPath } from "@/hooks/use-api-error-handler";

/**
 * Save/unsave a mentor to the student's wishlist. Saved state is loaded from the API on
 * mount; signed-out visitors are sent to log in when they press it.
 */
export function SaveMentorButton({
  mentorId,
  initialSaved,
  onChange,
  className,
}: {
  mentorId: string;
  /** Known saved state (skips the lookup), e.g. on the saved-mentors page. */
  initialSaved?: boolean;
  onChange?: (saved: boolean) => void;
  className?: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [saved, setSaved] = useState<boolean | null>(initialSaved ?? null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (initialSaved !== undefined) return;
    let cancelled = false;
    api.student.isSaved(mentorId).then(
      (isSaved) => {
        if (!cancelled) setSaved(isSaved);
      },
      // Signed out or not a student: show the default "Save" state.
      () => {
        if (!cancelled) setSaved(false);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [initialSaved, mentorId]);

  async function toggle() {
    const next = !saved;
    setPending(true);
    try {
      if (next) await api.student.saveMentor(mentorId);
      else await api.student.unsaveMentor(mentorId);
      setSaved(next);
      onChange?.(next);
      toast.success(next ? "Mentor saved" : "Removed from saved mentors");
    } catch (error) {
      if (isApiError(error) && error.kind === "unauthenticated") {
        router.push(loginRedirectPath(pathname));
      } else if (isApiError(error) && error.kind === "forbidden" && error.code === "permission_denied") {
        toast.error("Only student accounts can save mentors.");
      } else {
        toast.error("Couldn't update saved mentors", { description: getErrorMessage(error) });
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <Button
      type="button"
      variant="outline"
      onClick={toggle}
      disabled={pending || saved === null}
      aria-pressed={saved ?? false}
      className={className}
    >
      <Heart className={cn(saved && "fill-destructive text-destructive")} aria-hidden="true" />
      {saved ? "Saved" : "Save"}
    </Button>
  );
}
