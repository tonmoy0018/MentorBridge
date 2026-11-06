import Link from "next/link";
import { LogoMark } from "./logo";

const COLUMNS = [
  {
    title: "For students",
    links: [
      { href: "/mentors", label: "Find a mentor" },
      { href: "/#how-it-works", label: "How it works" },
      { href: "/signup/student", label: "Create a student account" },
    ],
  },
  {
    title: "For mentors",
    links: [
      { href: "/signup/mentor", label: "Become a mentor" },
      { href: "/#for-mentors", label: "Why mentor with us" },
      { href: "/#faq", label: "FAQ" },
    ],
  },
  {
    title: "Account",
    links: [
      { href: "/login", label: "Log in" },
      { href: "/signup", label: "Sign up" },
      { href: "/forgot-password", label: "Reset password" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="border-t bg-muted/40">
      <div className="container-page grid grid-cols-1 gap-10 py-12 md:grid-cols-[1.5fr_repeat(3,1fr)]">
        <div className="max-w-xs">
          <div className="flex items-center gap-2 font-semibold">
            <LogoMark />
            <span className="text-lg">MentorBridge</span>
          </div>
          <p className="mt-3 text-sm text-muted-foreground">
            One-to-one career guidance from experienced professionals, for students and early-career
            professionals.
          </p>
        </div>
        {COLUMNS.map((column) => (
          <nav key={column.title} aria-label={column.title}>
            <h2 className="text-sm font-semibold">{column.title}</h2>
            <ul className="mt-3 grid gap-2">
              {column.links.map((link) => (
                <li key={link.href}>
                  <Link href={link.href} className="text-sm text-muted-foreground hover:text-foreground">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>
      <div className="border-t">
        <p className="container-page py-6 text-xs text-muted-foreground">© MentorBridge. All rights reserved.</p>
      </div>
    </footer>
  );
}
