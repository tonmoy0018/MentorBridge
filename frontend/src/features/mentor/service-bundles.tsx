"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import type { MentorPackage, MentorService } from "@/lib/api/types";
import { api } from "@/lib/data/client";
import { formatMoney } from "@/lib/format";
import { applyServerErrors } from "@/lib/forms";
import { serviceFormats } from "@/lib/sessions";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { FormAlert } from "@/components/forms/form-alert";
import { FormField } from "@/components/forms/form-field";
import { useApiErrorHandler } from "@/hooks/use-api-error-handler";

const whole = (label: string, min: number, max: number) =>
  z
    .number({ error: `Enter ${label}.` })
    .int({ error: "Use a whole number." })
    .min(min, { error: `At least ${min}.` })
    .max(max, { error: `At most ${max}.` });

const bundleSchema = z.object({
  session_count: whole("how many sessions", 2, 24),
  discount_percent: whole("a discount (0 for none)", 0, 50),
  validity_days: whole("how many days", 7, 365),
  is_active: z.boolean(),
});
type BundleValues = z.infer<typeof bundleSchema>;

function BundleDialog({
  service,
  bundle,
  open,
  onOpenChange,
  onSaved,
}: {
  service: MentorService;
  bundle: MentorPackage | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: (bundle: MentorPackage) => void;
}) {
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<BundleValues>({
    resolver: zodResolver(bundleSchema),
    values: {
      session_count: bundle?.session_count ?? 4,
      discount_percent: bundle?.discount_percent ?? 10,
      validity_days: bundle?.validity_days ?? 60,
      is_active: bundle?.is_active ?? true,
    },
  });

  async function onSubmit(values: BundleValues) {
    setFormError(null);
    try {
      const saved = bundle
        ? await api.mentor.updatePackage(bundle.id, values)
        : await api.mentor.createPackage({ ...values, service_id: service.id });
      onSaved(saved);
      onOpenChange(false);
      toast.success(bundle ? "Option updated" : "Option added");
    } catch (error) {
      setFormError(applyServerErrors(error, setError, ["session_count", "discount_percent", "validity_days"]));
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{bundle ? "Edit multi-session option" : "Add a multi-session option"}</DialogTitle>
          <DialogDescription>
            Students pay once for several {service.title} sessions and book each when it suits them. The price follows
            your session price (online or in person), minus the discount. Changes apply to new purchases only.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid grid-cols-1 gap-4">
          {formError ? <FormAlert>{formError}</FormAlert> : null}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <FormField label="Sessions" error={errors.session_count?.message} required>
              {(props) => (
                <Input {...props} type="number" inputMode="numeric" min={2} max={24} {...register("session_count", { valueAsNumber: true })} />
              )}
            </FormField>
            <FormField label="Discount (%)" error={errors.discount_percent?.message} required>
              {(props) => (
                <Input {...props} type="number" inputMode="numeric" min={0} max={50} {...register("discount_percent", { valueAsNumber: true })} />
              )}
            </FormField>
            <FormField label="Use within (days)" error={errors.validity_days?.message} required>
              {(props) => (
                <Input {...props} type="number" inputMode="numeric" min={7} max={365} {...register("validity_days", { valueAsNumber: true })} />
              )}
            </FormField>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4 accent-primary" {...register("is_active")} />
            Offer this option to students
          </label>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Saving…" : "Save option"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** The multi-session options of one service, managed inside its card. */
export function ServiceBundles({
  service,
  bundles,
  onSaved,
  onDeleted,
}: {
  service: MentorService;
  bundles: MentorPackage[];
  onSaved: (bundle: MentorPackage) => void;
  onDeleted: (id: string) => void;
}) {
  const handleError = useApiErrorHandler();
  const [editing, setEditing] = useState<MentorPackage | null>(null);
  const [open, setOpen] = useState(false);
  const firstFormat = serviceFormats(service)[0] ?? "online";

  async function remove(bundle: MentorPackage) {
    try {
      await api.mentor.deletePackage(bundle.id);
      onDeleted(bundle.id);
      toast.success("Option deleted");
    } catch (error) {
      handleError(error, "Couldn't delete option");
    }
  }

  return (
    <div className="mt-3 border-t pt-3">
      <p className="text-sm font-medium">Multi-session options</p>
      <ul className="mt-2 grid gap-2">
        {bundles.map((b) => {
          const price = b.prices[firstFormat];
          return (
            <li key={b.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
              <span className={b.is_active ? "" : "text-muted-foreground line-through"}>
                {b.session_count} sessions{b.discount_percent > 0 ? ` · ${b.discount_percent}% off` : ""}
                {price ? ` · ${formatMoney(price)}` : ""} · within {b.validity_days} days
              </span>
              <Button size="sm" variant="link" className="h-auto p-0" onClick={() => { setEditing(b); setOpen(true); }}>
                Edit
              </Button>
              <Button size="sm" variant="link" className="h-auto p-0 text-destructive" onClick={() => remove(b)}>
                Delete
              </Button>
            </li>
          );
        })}
      </ul>
      <Button
        size="sm"
        variant="outline"
        className="mt-2"
        onClick={() => {
          setEditing(null);
          setOpen(true);
        }}
      >
        <Plus aria-hidden="true" />
        Add option
      </Button>
      <BundleDialog service={service} bundle={editing} open={open} onOpenChange={setOpen} onSaved={onSaved} />
    </div>
  );
}
