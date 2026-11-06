import { Compass } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/feedback/empty-state";
import { Logo } from "@/components/layout/logo";

export default function NotFound() {
  return (
    <main id="main" className="container-page flex flex-1 flex-col items-center py-16">
      <Logo className="mb-10" />
      <EmptyState
        className="w-full max-w-xl"
        icon={Compass}
        title="Page not found"
        description="The page you're looking for doesn't exist or has moved."
        action={
          <Button asChild>
            <Link href="/">Go to the homepage</Link>
          </Button>
        }
      />
    </main>
  );
}
