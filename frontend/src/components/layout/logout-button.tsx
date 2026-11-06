"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/data/client";
import { getErrorMessage } from "@/lib/api/errors";
import { cn } from "@/lib/utils";

/** Ends the Django session, then returns to the homepage. */
export function useLogout() {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function logout() {
    setPending(true);
    try {
      await api.auth.logout();
      router.push("/");
      router.refresh();
    } catch (error) {
      toast.error("Couldn't log out", { description: getErrorMessage(error) });
    } finally {
      setPending(false);
    }
  }

  return { logout, pending, label: "Log out" };
}

export function LogoutButton({ className }: { className?: string }) {
  const { logout, pending, label } = useLogout();
  return (
    <button
      type="button"
      onClick={logout}
      disabled={pending}
      className={cn(
        "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-60",
        className,
      )}
    >
      <LogOut className="size-4" aria-hidden="true" />
      {pending ? "Logging out…" : label}
    </button>
  );
}
