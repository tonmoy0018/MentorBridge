import { ShieldCheck } from "lucide-react";

/** Reminder that hiding admin UI is not the security boundary. */
export function AdminSecurityNote() {
  return (
    <p className="flex items-start gap-2 text-xs text-muted-foreground">
      <ShieldCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
      Every admin action is authorised by the API for admin accounts and recorded in the audit log.
    </p>
  );
}
