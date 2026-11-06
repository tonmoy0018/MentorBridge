import { AlertCircle, CheckCircle2 } from "lucide-react";
import type { ReactNode } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

/** Form-level message (non-field errors, success confirmations). */
export function FormAlert({
  variant = "error",
  title,
  children,
}: {
  variant?: "error" | "success";
  title?: string;
  children: ReactNode;
}) {
  const isError = variant === "error";
  return (
    <Alert
      variant={isError ? "destructive" : "default"}
      role={isError ? "alert" : "status"}
      className={isError ? undefined : "border-success/30 bg-success-soft text-success"}
    >
      {isError ? <AlertCircle aria-hidden="true" /> : <CheckCircle2 aria-hidden="true" />}
      {title ? <AlertTitle>{title}</AlertTitle> : null}
      <AlertDescription className={isError ? undefined : "text-success"}>{children}</AlertDescription>
    </Alert>
  );
}
