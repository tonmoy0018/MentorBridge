import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/data/server";

/** Sends visitors who already have a session to their dashboard. Render inside <Suspense>. */
export async function RedirectIfSignedIn() {
  const user = await getCurrentUser().catch(() => null);
  if (user) redirect("/dashboard");
  return null;
}
