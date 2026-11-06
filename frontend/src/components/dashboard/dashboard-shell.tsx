"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import type { CurrentUser, Role } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { AccountMenu } from "@/components/layout/account-menu";
import { Logo } from "@/components/layout/logo";
import { LogoutButton } from "@/components/layout/logout-button";
import { CurrentUserProvider, useCurrentUser } from "./current-user";
import { DASHBOARD_NAV, ROLE_LABEL } from "./nav-config";

function isActive(pathname: string, href: string, root: string) {
  return href === root ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
}

function DashboardNav({ role, onNavigate }: { role: Role; onNavigate?: () => void }) {
  const pathname = usePathname();
  const items = DASHBOARD_NAV[role];
  const root = items[0]!.href;
  return (
    <nav aria-label={`${ROLE_LABEL[role]} dashboard`}>
      <ul className="grid gap-1">
        {items.map((item) => {
          const active = isActive(pathname, item.href, root);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-secondary text-secondary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <item.icon className="size-4" aria-hidden="true" />
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function ShellHeader({ role }: { role: Role }) {
  const { user } = useCurrentUser();
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur">
      <div className="mx-auto flex h-16 w-full max-w-7xl items-center gap-3 px-4 sm:px-6">
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open dashboard menu">
              <Menu className="size-5" aria-hidden="true" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-72">
            <SheetHeader>
              <SheetTitle>{ROLE_LABEL[role]} dashboard</SheetTitle>
              <SheetDescription className="sr-only">Dashboard navigation</SheetDescription>
            </SheetHeader>
            <div className="px-4">
              <DashboardNav role={role} onNavigate={() => setOpen(false)} />
            </div>
            <div className="mt-auto border-t p-4">
              <LogoutButton />
            </div>
          </SheetContent>
        </Sheet>
        <Logo className="max-sm:[&>span]:hidden" />
        <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
          {ROLE_LABEL[role]}
        </span>
        <div className="ml-auto flex items-center gap-2">
          {role === "student" ? (
            <Button asChild variant="ghost" className="max-sm:hidden">
              <Link href="/mentors">Find a mentor</Link>
            </Button>
          ) : null}
          <AccountMenu user={user} />
        </div>
      </div>
    </header>
  );
}

export function DashboardShell({ user, role, children }: { user: CurrentUser; role: Role; children: ReactNode }) {
  return (
    <CurrentUserProvider user={user}>
      <div className="flex min-h-svh flex-col bg-muted/30">
        <ShellHeader role={role} />
        <div className="mx-auto flex w-full max-w-7xl flex-1">
          <aside className="sticky top-16 hidden h-[calc(100svh-4rem)] w-60 shrink-0 border-r p-4 lg:block">
            <DashboardNav role={role} />
          </aside>
          <main id="main" className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
            {children}
          </main>
        </div>
      </div>
    </CurrentUserProvider>
  );
}
