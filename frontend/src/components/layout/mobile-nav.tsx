"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import type { CurrentUser } from "@/lib/api/types";
import { dashboardPathFor } from "@/lib/routes";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { LogoutButton } from "./logout-button";
import { MAIN_NAV } from "./nav-links";

export function MobileNav({ user }: { user: CurrentUser | null }) {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open menu">
          <Menu className="size-5" aria-hidden="true" />
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="w-[85vw] max-w-sm">
        <SheetHeader>
          <SheetTitle>Menu</SheetTitle>
          <SheetDescription className="sr-only">Site navigation</SheetDescription>
        </SheetHeader>
        <nav aria-label="Mobile" className="grid gap-1 px-4">
          {MAIN_NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={close}
              className="rounded-lg px-3 py-2.5 text-base font-medium hover:bg-muted"
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="mt-auto grid gap-2 border-t p-4">
          {user ? (
            <>
              <Button asChild>
                <Link href={dashboardPathFor(user.role)} onClick={close}>
                  Go to dashboard
                </Link>
              </Button>
              <LogoutButton />
            </>
          ) : (
            <>
              <Button asChild>
                <Link href="/signup" onClick={close}>
                  Sign up
                </Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/login" onClick={close}>
                  Log in
                </Link>
              </Button>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
