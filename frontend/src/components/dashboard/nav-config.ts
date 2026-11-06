import {
  BadgeCheck,
  BarChart3,
  CalendarDays,
  Clock,
  CreditCard,
  Flag,
  Heart,
  LayoutDashboard,
  Mail,
  MessageSquareText,
  Package,
  ScrollText,
  Settings,
  Target,
  UserRound,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import type { Role } from "@/lib/api/types";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export const DASHBOARD_NAV: Record<Role, NavItem[]> = {
  student: [
    { href: "/dashboard/student", label: "Overview", icon: LayoutDashboard },
    { href: "/dashboard/student/bookings", label: "Bookings", icon: CalendarDays },
    { href: "/dashboard/student/saved-mentors", label: "Saved mentors", icon: Heart },
    { href: "/dashboard/student/goals", label: "Goals", icon: Target },
    { href: "/dashboard/student/settings", label: "Settings", icon: Settings },
  ],
  mentor: [
    { href: "/dashboard/mentor", label: "Overview", icon: LayoutDashboard },
    { href: "/dashboard/mentor/profile", label: "Profile", icon: UserRound },
    { href: "/dashboard/mentor/services", label: "Services", icon: Package },
    { href: "/dashboard/mentor/availability", label: "Availability", icon: Clock },
    { href: "/dashboard/mentor/bookings", label: "Bookings", icon: CalendarDays },
    { href: "/dashboard/mentor/earnings", label: "Earnings", icon: Wallet },
    { href: "/dashboard/mentor/settings", label: "Settings", icon: Settings },
  ],
  admin: [
    { href: "/dashboard/admin", label: "Overview", icon: BarChart3 },
    { href: "/dashboard/admin/users", label: "Users", icon: Users },
    { href: "/dashboard/admin/verification", label: "Verification", icon: BadgeCheck },
    { href: "/dashboard/admin/bookings", label: "Bookings", icon: CalendarDays },
    { href: "/dashboard/admin/payments", label: "Payments", icon: CreditCard },
    { href: "/dashboard/admin/reports", label: "Reports", icon: Flag },
    { href: "/dashboard/admin/reviews", label: "Reviews", icon: MessageSquareText },
    { href: "/dashboard/admin/audit-log", label: "Audit log", icon: ScrollText },
    { href: "/dashboard/admin/emails", label: "Emails", icon: Mail },
  ],
};

export const ROLE_LABEL: Record<Role, string> = { student: "Student", mentor: "Mentor", admin: "Admin" };
