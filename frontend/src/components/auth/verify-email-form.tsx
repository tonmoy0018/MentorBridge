"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { isApiError } from "@/lib/api/errors";
import { api } from "@/lib/data/client";
import { Button } from "@/components/ui/button";
import { FormAlert } from "@/components/forms/form-alert";

/**
 * Confirms the email from the link Django sends. Confirmation needs a click (a POST), so link
 * scanners that merely open the URL can't use up the single-use token.
 */
export function VerifyEmailForm() {
  const searchParams = useSearchParams();
  const uid = searchParams.get("uid");
  const token = searchParams.get("token");
  const [state, setState] = useState<"idle" | "pending" | "done" | "invalid" | "error">(
    uid && token ? "idle" : "invalid",
  );
  const [message, setMessage] = useState<string | null>(null);

  async function confirm() {
    if (!uid || !token) return;
    setState("pending");
    try {
      await api.auth.verifyEmail({ uid, token });
      setState("done");
    } catch (error) {
      if (isApiError(error) && error.code === "invalid_token") {
        setState("invalid");
      } else {
        setMessage(isApiError(error) ? error.message : null);
        setState("error");
      }
    }
  }

  if (state === "done") {
    return (
      <div className="grid gap-5">
        <FormAlert variant="success" title="Email confirmed">
          Thanks, your email address is verified.
        </FormAlert>
        <Button asChild size="lg">
          <Link href="/dashboard">Go to your dashboard</Link>
        </Button>
      </div>
    );
  }

  if (state === "invalid") {
    return (
      <div className="grid gap-5">
        <FormAlert title="This link is invalid or has expired">
          Verification links can only be used once. Log in and request a new one from your account settings.
        </FormAlert>
        <Button asChild size="lg" variant="outline">
          <Link href="/login">Log in</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="grid gap-5">
      {state === "error" ? <FormAlert>{message ?? "We couldn't confirm your email. Please try again."}</FormAlert> : null}
      <Button size="lg" onClick={confirm} disabled={state === "pending"}>
        {state === "pending" ? "Confirming…" : "Confirm my email"}
      </Button>
    </div>
  );
}
