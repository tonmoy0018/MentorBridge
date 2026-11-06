"use client";

import { ChevronDown, LayoutDashboard, LogOut, Settings } from "lucide-react";
import Link from "next/link";
import type { CurrentUser } from "@/lib/api/types";
import { dashboardPathFor } from "@/lib/routes";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MentorAvatar } from "@/components/mentors/mentor-avatar";
import { useLogout } from "./logout-button";

export function AccountMenu({ user }: { user: CurrentUser }) {
  const { logout, label } = useLogout();
  const name = `${user.first_name} ${user.last_name}`.trim() || user.email;
  const dashboard = dashboardPathFor(user.role);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex items-center gap-2 rounded-full p-1 pr-2 hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none">
        <MentorAvatar name={name} src={null} size="sm" />
        <span className="max-w-32 truncate text-sm font-medium max-sm:sr-only">{user.first_name || name}</span>
        <span className="sr-only">Open account menu</span>
        <ChevronDown className="size-4 text-muted-foreground" aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="font-normal">
          <span className="block truncate font-medium">{name}</span>
          <span className="block truncate text-xs text-muted-foreground">{user.email}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href={dashboard}>
            <LayoutDashboard aria-hidden="true" />
            Dashboard
          </Link>
        </DropdownMenuItem>
        {user.role !== "admin" ? (
          <DropdownMenuItem asChild>
            <Link href={`${dashboard}/settings`}>
              <Settings aria-hidden="true" />
              Settings
            </Link>
          </DropdownMenuItem>
        ) : null}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={logout}>
          <LogOut aria-hidden="true" />
          {label}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
