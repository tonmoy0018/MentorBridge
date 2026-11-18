"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Clock, MapPin, Package, Pencil, Plus, Video } from "lucide-react";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { SERVICE_DURATIONS, type MentorService, type Money, type ServiceDuration } from "@/lib/api/types";
import { api } from "@/lib/data/client";
import { formatDuration, formatMoney } from "@/lib/format";
import { applyServerErrors } from "@/lib/forms";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { PageHeader } from "@/components/common/page-header";
import { QueryView } from "@/components/common/query-view";
import { StatusBadge } from "@/components/common/status-badge";
import { EmptyState } from "@/components/feedback/empty-state";
import { FormAlert } from "@/components/forms/form-alert";
import { FormField } from "@/components/forms/form-field";
import { NativeSelect } from "@/components/forms/native-select";
import { PriceDisplay } from "@/components/mentors/price-display";
import { useApiErrorHandler } from "@/hooks/use-api-error-handler";
import { useApiQuery } from "@/hooks/use-api-query";
import { ServiceBundles } from "./service-bundles";
import { SeminarsManager } from "./seminars-manager";

const money = (label: string) =>
  z
    .number({ error: `Enter ${label} (0 for none).` })
    .min(0, { error: "Amounts can't be negative." })
    .max(10_000, { error: "Enter $10,000 or less." })
    .refine((v) => Math.abs(v * 100 - Math.round(v * 100)) < 1e-6, { error: "Use at most two decimal places." });

const serviceSchema = z
  .object({
  title: z.string().trim().min(3, { error: "Give the service a short title." }).max(120),
  description: z
    .string()
    .trim()
    .min(10, { error: "Describe what the student gets in at least 10 characters." })
    .max(1000, { error: "Keep the description under 1,000 characters." }),
  duration_minutes: z
    .string()
    .refine((v) => (SERVICE_DURATIONS as readonly number[]).includes(Number(v)), { error: "Choose a length." }),
  price: money("a price"),
  is_active: z.boolean(),
  online: z.boolean(),
  in_person: z.boolean(),
  in_person_extra: money("an amount"),
  in_person_area: z.string().trim().max(120),
  })
  .refine((v) => v.online || v.in_person, { path: ["online"], error: "Offer the session online, in person, or both." })
  .refine((v) => !v.in_person || v.in_person_area.length >= 3, {
    path: ["in_person_area"],
    error: "Say where you meet, e.g. a neighbourhood or city.",
  });
type ServiceValues = z.infer<typeof serviceSchema>;

function ServiceDialog({
  service,
  minPrice,
  open,
  onOpenChange,
  onSaved,
}: {
  service: MentorService | null;
  /** From GET /config/: the lowest price a session may have. */
  minPrice: Money | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: (service: MentorService) => void;
}) {
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    control,
    formState: { errors, isSubmitting },
  } = useForm<ServiceValues>({
    resolver: zodResolver(serviceSchema),
    values: {
      title: service?.title ?? "",
      description: service?.description ?? "",
      duration_minutes: String(service?.duration_minutes ?? 60),
      price: service ? service.price.amount_cents / 100 : 50,
      is_active: service?.is_active ?? true,
      online: service?.online ?? true,
      in_person: service?.in_person ?? false,
      in_person_extra: service ? service.in_person_extra.amount_cents / 100 : 0,
      in_person_area: service?.in_person_area ?? "",
    },
  });
  const inPerson = useWatch({ control, name: "in_person" });

  async function onSubmit(values: ServiceValues) {
    setFormError(null);
    if (minPrice && Math.round(values.price * 100) < minPrice.amount_cents) {
      setError("price", { message: `Set a price of at least ${formatMoney(minPrice, { showFree: false })}.` });
      return;
    }
    const input = {
      title: values.title,
      description: values.description,
      duration_minutes: Number(values.duration_minutes) as ServiceDuration,
      price_cents: Math.round(values.price * 100),
      is_active: values.is_active,
      online: values.online,
      in_person: values.in_person,
      in_person_extra_cents: values.in_person ? Math.round(values.in_person_extra * 100) : 0,
      in_person_area: values.in_person ? values.in_person_area : "",
    };
    try {
      const saved = service ? await api.mentor.updateService(service.id, input) : await api.mentor.createService(input);
      onSaved(saved);
      onOpenChange(false);
      toast.success(service ? "Service updated" : "Service added");
    } catch (error) {
      setFormError(
        applyServerErrors(error, setError, [
          "title",
          "description",
          "duration_minutes",
          "online",
          "in_person",
          "in_person_area",
        ]),
      );
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{service ? "Edit service" : "Add a service"}</DialogTitle>
          <DialogDescription>
            Changes apply to new bookings. Existing bookings keep the price and length they were booked at.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid grid-cols-1 gap-4">
          {formError ? <FormAlert>{formError}</FormAlert> : null}
          <FormField label="Title" error={errors.title?.message} required>
            {(props) => <Input {...props} placeholder="e.g. Mock interview" {...register("title")} />}
          </FormField>
          <FormField label="What's included" error={errors.description?.message} required>
            {(props) => <Textarea {...props} rows={3} {...register("description")} />}
          </FormField>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField label="Length" error={errors.duration_minutes?.message} required>
              {(props) => (
                <NativeSelect {...props} {...register("duration_minutes")}>
                  {SERVICE_DURATIONS.map((d) => (
                    <option key={d} value={d}>
                      {formatDuration(d)}
                    </option>
                  ))}
                </NativeSelect>
              )}
            </FormField>
            <FormField
              label="Price (USD)"
              error={errors.price?.message}
              description={
                minPrice && minPrice.amount_cents > 0
                  ? `At least ${formatMoney(minPrice, { showFree: false })}.`
                  : "Set 0 for a free session."
              }
              required
            >
              {(props) => (
                <Input {...props} type="number" inputMode="decimal" min={0} step="0.01" {...register("price", { valueAsNumber: true })} />
              )}
            </FormField>
          </div>
          <fieldset className="grid gap-3 rounded-lg border p-4">
            <legend className="px-1 text-sm font-medium">Where the session happens</legend>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4 accent-primary" {...register("online")} />
              Online (video call)
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4 accent-primary" {...register("in_person")} />
              In person (meet up)
            </label>
            {errors.online?.message ? <p className="text-sm text-destructive">{errors.online.message}</p> : null}
            {inPerson ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <FormField
                  label="Extra for in person (USD)"
                  error={errors.in_person_extra?.message}
                  description="Added to the price, e.g. for travel. 0 for none."
                >
                  {(props) => (
                    <Input
                      {...props}
                      type="number"
                      inputMode="decimal"
                      min={0}
                      step="0.01"
                      {...register("in_person_extra", { valueAsNumber: true })}
                    />
                  )}
                </FormField>
                <FormField
                  label="Area you meet in"
                  error={errors.in_person_area?.message}
                  description="Shown publicly. Never your home address: you'll share the exact place per booking."
                  required
                >
                  {(props) => <Input {...props} placeholder="e.g. Gulshan, Dhaka" {...register("in_person_area")} />}
                </FormField>
              </div>
            ) : null}
          </fieldset>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4 accent-primary" {...register("is_active")} />
            Available for booking
          </label>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Saving…" : "Save service"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ServicesManager() {
  const query = useApiQuery("mentor:services", () => api.mentor.services());
  const handleError = useApiErrorHandler();
  const [editing, setEditing] = useState<MentorService | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const bundles = useApiQuery("mentor:packages", () => api.mentor.packages());
  const config = useApiQuery("config", () => api.config.get());
  const minPrice = config.data?.min_session_price ?? null;

  const upsert = (service: MentorService) =>
    query.mutate((list) =>
      list.some((s) => s.id === service.id) ? list.map((s) => (s.id === service.id ? service : s)) : [...list, service],
    );

  async function toggleActive(service: MentorService, isActive: boolean) {
    try {
      upsert(await api.mentor.updateService(service.id, { is_active: isActive }));
      toast.success(isActive ? "Service is bookable" : "Service hidden from students");
    } catch (error) {
      handleError(error, "Couldn't update service");
    }
  }

  const open = (service: MentorService | null) => {
    setEditing(service);
    setDialogOpen(true);
  };

  return (
    <div className="grid grid-cols-1 gap-6">
      <PageHeader
        title="Services"
        description="The sessions students can book with you, with their length and price."
        actions={
          <Button onClick={() => open(null)}>
            <Plus aria-hidden="true" />
            Add service
          </Button>
        }
      />
      <QueryView query={query} errorTitle="Couldn't load your services">
        {(services) =>
          services.length === 0 ? (
            <EmptyState
              icon={Package}
              title="No services yet"
              description="Add at least one service so students can book you — for example a 30-minute career chat."
              action={<Button onClick={() => open(null)}>Add your first service</Button>}
            />
          ) : (
            <>
            <ul className="grid grid-cols-1 gap-3">
              {services.map((service) => (
                <li key={service.id} className="flex flex-col gap-4 rounded-xl border bg-card p-5 sm:flex-row sm:items-center">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="font-semibold">{service.title}</h2>
                      {service.is_active ? (
                        <StatusBadge tone="success">Bookable</StatusBadge>
                      ) : (
                        <StatusBadge tone="neutral">Hidden</StatusBadge>
                      )}
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">{service.description}</p>
                    <p className="mt-2 flex items-center gap-3 text-sm">
                      <span className="flex items-center gap-1.5 text-muted-foreground">
                        <Clock className="size-4" aria-hidden="true" />
                        {formatDuration(service.duration_minutes)}
                      </span>
                      <PriceDisplay price={service.price} />
                    </p>
                    <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
                      {service.online ? (
                        <span className="flex items-center gap-1.5">
                          <Video className="size-4" aria-hidden="true" />
                          Online
                        </span>
                      ) : null}
                      {service.in_person ? (
                        <span className="flex items-center gap-1.5">
                          <MapPin className="size-4" aria-hidden="true" />
                          In person in {service.in_person_area}
                          {service.in_person_extra.amount_cents > 0
                            ? ` (+${formatMoney(service.in_person_extra)})`
                            : ""}
                        </span>
                      ) : null}
                    </p>
                    <ServiceBundles
                      service={service}
                      bundles={(bundles.data ?? []).filter((b) => b.service.id === service.id)}
                      onSaved={(saved) =>
                        bundles.mutate((list) =>
                          list.some((b) => b.id === saved.id)
                            ? list.map((b) => (b.id === saved.id ? saved : b))
                            : [...list, saved],
                        )
                      }
                      onDeleted={(id) => bundles.mutate((list) => list.filter((b) => b.id !== id))}
                    />
                  </div>
                  <div className="flex items-center gap-4 sm:self-start">
                    <label className="flex items-center gap-2 text-sm">
                      <Switch
                        checked={service.is_active}
                        onCheckedChange={(checked) => toggleActive(service, checked)}
                        aria-label={`${service.title} is bookable`}
                      />
                      Bookable
                    </label>
                    <Button variant="outline" size="sm" onClick={() => open(service)}>
                      <Pencil aria-hidden="true" />
                      Edit
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
            <SeminarsManager services={services} minPrice={minPrice} />
            </>
          )
        }
      </QueryView>
      <ServiceDialog
        service={editing}
        minPrice={minPrice}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSaved={upsert}
      />
    </div>
  );
}
