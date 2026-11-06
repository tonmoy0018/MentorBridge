import { UserX } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/feedback/empty-state";

export default function MentorNotFound() {
  return (
    <div className="container-page py-16">
      <EmptyState
        icon={UserX}
        title="Mentor not found"
        description="This profile doesn't exist or is no longer available."
        action={
          <Button asChild>
            <Link href="/mentors">Browse mentors</Link>
          </Button>
        }
      />
    </div>
  );
}
