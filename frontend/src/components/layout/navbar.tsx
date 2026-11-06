import Link from "next/link";
import { Suspense } from "react";
import { getCurrentUser } from "@/lib/data/server";
import { dashboardPathFor } from "@/lib/routes";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { AccountMenu } from "./account-menu";
import { Logo } from "./logo";
import { MobileNav } from "./mobile-nav";
import { MAIN_NAV } from "./nav-links";

export function Navbar() {
  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/80">
      <div className="container-page flex h-16 items-center gap-8">
        <Logo />
        <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
          {MAIN_NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          {/* The session is read at request time, so the account area streams in. */}
          <Suspense fallback={<Skeleton className="h-9 w-40 rounded-lg" />}>
            <NavbarAccount />
          </Suspense>
        </div>
      </div>
    </header>
  );
}

async function NavbarAccount() {
  // A failure to reach the API must not break public pages: show the signed-out state.
  const user = await getCurrentUser().catch(() => null);

  return (
    <>
      <div className="hidden items-center gap-2 md:flex">
        {user ? (
          <>
            <Button asChild variant="outline">
              <Link href={dashboardPathFor(user.role)}>Dashboard</Link>
            </Button>
            <AccountMenu user={user} />
          </>
        ) : (
          <>
            <Button asChild variant="ghost">
              <Link href="/login">Log in</Link>
            </Button>
            <Button asChild>
              <Link href="/signup">Sign up</Link>
            </Button>
          </>
        )}
      </div>
      <MobileNav user={user} />
    </>
  );
}
