"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { CalendarDays, MapPin, Pencil, Plus, Users, Video } from "lucide-react";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import {
  SERVICE_DURATIONS,
  type MentorSeminar,
  type MentorService,
  type Money,
  type ServiceDuration,
} from "@/lib/api/types";
import { api } from "@/lib/data/client";
import { formatDate, formatDuration, formatMoney, formatTime, timeZoneLabel } from "@/lib/format";
import { applyServerErrors } from "@/lib/forms";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { QueryView } from "@/components/common/query-view";
import { StatusBadge } from "@/components/common/status-badge";
import { ConfirmationDialog } from "@/components/feedback/confirmation-dialog";
import { FormAlert } from "@/components/forms/form-alert";
import { FormField } from "@/components/forms/form-field";
import { NativeSelect } from "@/components/forms/native-select";
import { useApiQuery } from "@/hooks/use-api-query";

/** "YYYY-MM-DDTHH:mm" in the browser's time zone, for a datetime-local input. */
function toLocalInput(iso: string) {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const seminarSchema = z
  .object({
    service_id: z.string().min(1, { error: "Choose a session." }),
    title: z.string().trim().max(120),
    description: z.string().trim().max(1000, { error: "Keep the description under 1,000 characters." }),
    start: z.string().min(1, { error: "Choose a date and time." }),
    duration_minutes: z.string(),
    capacity: z
      .number({ error: "Enter how many seats." })
      .int({ error: "Use a whole number." })
      .min(2, { error: "At least 2 seats." })
      .max(100, { error: "At most 100 seats." }),
    price: z
      .number({ error: "Enter a price (0 for free)." })
      .min(0, { error: "Price can't be negative." })
      .max(10_000, { error: "Enter $10,000 or less." })
      .refine((v) => Math.abs(v * 100 - Math.round(v * 100)) < 1e-6, { error: "Use at most two decimal places." }),
    format: z.enum(["online", "in_person"]),
    in_person_area: z.string().trim().max(120),
    meeting_place: z.string().trim().max(300),
    meeting_url: z.string().trim().max(300),
  })
  .refine((v) => v.format !== "in_person" || v.in_person_area.length >= 3, {
    path: ["in_person_area"],
    error: "Say where the seminar takes place, e.g. a neighbourhood.",
  });
type SeminarValues = z.infer<typeof seminarSchema>;

function SeminarDialog({
  seminar,
  services,
  minPrice,
  open,
  onOpenChange,
  onSaved,
}: {
  seminar: MentorSeminar | null;
  services: MentorService[];
  minPrice: Money | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: (seminar: MentorSeminar) => void;
}) {
  const [formError, setFormError] = useState<string | null>(null);
  const choices = services.filter((s) => s.is_active || s.id === seminar?.service.id);
  // Students registered for these terms, so they're fixed (the API enforces the same).
  const locked = Boolean(seminar && seminar.seats_taken > 0);
  const {
    register,
    handleSubmit,
    setError,
    control,
    formState: { errors, isSubmitting },
  } = useForm<SeminarValues>({
    resolver: zodResolver(seminarSchema),
    values: {
      service_id: seminar?.service.id ?? choices[0]?.id ?? "",
      title: seminar?.title ?? "",
      description: seminar?.description ?? "",
      start: seminar ? toLocalInput(seminar.start_at) : "",
      duration_minutes: String(seminar?.duration_minutes ?? 60),
      capacity: seminar?.capacity ?? 10,
      price: seminar ? seminar.price.amount_cents / 100 : 0,
      format: seminar?.format ?? "online",
      in_person_area: seminar?.in_person_area ?? "",
      meeting_place: seminar?.meeting_place ?? "",
      meeting_url: seminar?.meeting_url ?? "",
    },
  });
  const format = useWatch({ control, name: "format" });

  async function onSubmit(values: SeminarValues) {
    setFormError(null);
    if (minPrice && Math.round(values.price * 100) < minPrice.amount_cents) {
      setError("price", { message: `Set a price of at least ${formatMoney(minPrice, { showFree: false })}.` });
      return;
    }
    const input = {
      service_id: values.service_id,
      title: values.title,
      description: values.description,
      start_at: new Date(values.start).toISOString(),
      duration_minutes: Number(values.duration_minutes) as ServiceDuration,
      capacity: values.capacity,
      price_cents: Math.round(values.price * 100),
      format: values.format,
      in_person_area: values.format === "in_person" ? values.in_person_area : "",
      meeting_place: values.format === "in_person" ? values.meeting_place : "",
      meeting_url: values.format === "online" ? values.meeting_url : "",
    };
    try {
      const saved = seminar
        ? await api.mentor.updateSeminar(seminar.id, input)
        : await api.mentor.createSeminar(input);
      onSaved(saved);
      onOpenChange(false);
      toast.success(seminar ? "Seminar updated" : "Seminar scheduled");
    } catch (error) {
      setFormError(
        applyServerErrors(error, setError, ["service_id", "title", "capacity", "in_person_area", "meeting_url"]),
      );
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{seminar ? "Edit seminar" : "Schedule a group seminar"}</DialogTitle>
          <DialogDescription>
            One of your sessions for several students at a fixed time. Students register for a seat; you don&apos;t
            need to accept each one.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid grid-cols-1 gap-4">
          {formError ? <FormAlert>{formError}</FormAlert> : null}
          {locked ? (
            <p role="note" className="rounded-lg bg-muted/60 p-3 text-sm text-muted-foreground">
              Students have registered, so the session, time, length, price and format are fixed. To change them,
              cancel this seminar and schedule a new one.
            </p>
          ) : null}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField label="Session" error={errors.service_id?.message} required>
              {(props) => (
                <NativeSelect {...props} disabled={locked} {...register("service_id")}>
                  {choices.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.title}
                    </option>
                  ))}
                </NativeSelect>
              )}
            </FormField>
            <FormField label="Title" error={errors.title?.message} description="Leave empty to use the session's name.">
              {(props) => <Input {...props} placeholder="e.g. Group mock interview" {...register("title")} />}
            </FormField>
          </div>
          <FormField label="Description" error={errors.description?.message}>
            {(props) => <Textarea {...props} rows={2} {...register("description")} />}
          </FormField>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField
              label="Date and time"
              error={errors.start?.message}
              description={`In your browser's time zone (${timeZoneLabel(undefined)}).`}
              required
            >
              {(props) => <Input {...props} type="datetime-local" disabled={locked} {...register("start")} />}
            </FormField>
            <FormField label="Length" error={errors.duration_minutes?.message} required>
              {(props) => (
                <NativeSelect {...props} disabled={locked} {...register("duration_minutes")}>
                  {SERVICE_DURATIONS.map((d) => (
                    <option key={d} value={d}>
                      {formatDuration(d)}
                    </option>
                  ))}
                </NativeSelect>
              )}
            </FormField>
            <FormField label="Seats" error={errors.capacity?.message} required>
              {(props) => (
                <Input {...props} type="number" inputMode="numeric" min={2} max={100} {...register("capacity", { valueAsNumber: true })} />
              )}
            </FormField>
            <FormField
              label="Price per seat (USD)"
              error={errors.price?.message}
              description={
                minPrice && minPrice.amount_cents > 0
                  ? `At least ${formatMoney(minPrice, { showFree: false })}.`
                  : "0 for free."
              }
              required
            >
              {(props) => (
                <Input
                  {...props}
                  type="number"
                  inputMode="decimal"
                  min={0}
                  step="0.01"
                  disabled={locked}
                  {...register("price", { valueAsNumber: true })}
                />
              )}
            </FormField>
          </div>
          <fieldset className="grid gap-3 rounded-lg border p-4" disabled={locked}>
            <legend className="px-1 text-sm font-medium">Where</legend>
            <label className="flex items-center gap-2 text-sm">
              <input type="radio" value="online" className="size-4 accent-primary" {...register("format")} />
              Online
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="radio" value="in_person" className="size-4 accent-primary" {...register("format")} />
              In person
            </label>
          </fieldset>
          {format === "in_person" ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FormField
                label="Area"
                error={errors.in_person_area?.message}
                description="Shown publicly, e.g. a neighbourhood."
                required
              >
                {(props) => <Input {...props} placeholder="e.g. Gulshan, Dhaka" {...register("in_person_area")} />}
              </FormField>
              <FormField
                label="Exact place"
                error={errors.meeting_place?.message}
                description="Only registered students see it. Somewhere public."
              >
                {(props) => <Input {...props} placeholder="Venue, room, address" {...register("meeting_place")} />}
              </FormField>
            </div>
          ) : (
            <FormField
              label="Meeting link"
              error={errors.meeting_url?.message}
              description="Leave empty to use your default meeting link."
            >
              {(props) => <Input {...props} type="url" placeholder="https://" {...register("meeting_url")} />}
            </FormField>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Saving…" : seminar ? "Save seminar" : "Schedule seminar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

const STATUS_BADGE = {
  scheduled: <StatusBadge tone="success">Scheduled</StatusBadge>,
  completed: <StatusBadge tone="neutral">Completed</StatusBadge>,
  cancelled: <StatusBadge tone="neutral">Cancelled</StatusBadge>,
} as const;

function SeminarCard({
  seminar,
  now,
  onEdit,
  onCancel,
  onComplete,
}: {
  seminar: MentorSeminar;
  /** When the page loaded (render must stay pure). */
  now: number;
  onEdit: () => void;
  onCancel: () => void;
  onComplete: () => void;
}) {
  const started = new Date(seminar.start_at).getTime() <= now;
  const scheduled = seminar.status === "scheduled";
  return (
    <li className="rounded-xl border bg-card p-5">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-semibold">{seminar.title}</h3>
        {STATUS_BADGE[seminar.status]}
      </div>
      <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <CalendarDays className="size-4" aria-hidden="true" />
          {formatDate(seminar.start_at)}, {formatTime(seminar.start_at)} · {formatDuration(seminar.duration_minutes)}
        </span>
        <span className="flex items-center gap-1.5">
          {seminar.format === "in_person" ? (
            <MapPin className="size-4" aria-hidden="true" />
          ) : (
            <Video className="size-4" aria-hidden="true" />
          )}
          {seminar.format === "in_person" ? `In person in ${seminar.in_person_area}` : "Online"}
        </span>
        <span className="flex items-center gap-1.5">
          <Users className="size-4" aria-hidden="true" />
          {seminar.seats_taken} of {seminar.capacity} seats taken
        </span>
        <span>{formatMoney(seminar.price, { showFree: true })} per seat</span>
      </p>
      {seminar.format === "in_person" && scheduled && !seminar.meeting_place ? (
        <p className="mt-2 text-sm text-warning">Add the exact place so registered students know where to go.</p>
      ) : null}
      {seminar.status === "cancelled" && seminar.cancellation_reason ? (
        <p className="mt-2 text-sm text-muted-foreground">Reason: {seminar.cancellation_reason}</p>
      ) : null}
      {seminar.attendees.length > 0 ? (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer font-medium">Who&apos;s coming ({seminar.attendees.length})</summary>
          <ul className="mt-2 grid gap-1 text-muted-foreground">
            {seminar.attendees.map((a) => (
              <li key={a.booking_id}>
                {a.display_name}
                {a.status === "pending_payment" ? " (paying)" : ""}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      {scheduled ? (
        <div className="mt-4 flex flex-wrap gap-2 border-t pt-4">
          {started ? (
            <Button size="sm" variant="outline" onClick={onComplete}>
              Mark as completed
            </Button>
          ) : (
            <>
              <Button size="sm" variant="outline" onClick={onEdit}>
                <Pencil aria-hidden="true" />
                Edit
              </Button>
              <Button size="sm" variant="ghost" className="text-destructive" onClick={onCancel}>
                Cancel seminar
              </Button>
            </>
          )}
        </div>
      ) : null}
    </li>
  );
}

export function SeminarsManager({ services, minPrice }: { services: MentorService[]; minPrice: Money | null }) {
  const query = useApiQuery("mentor:seminars", () => api.mentor.seminars());
  const [editing, setEditing] = useState<MentorSeminar | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [cancelling, setCancelling] = useState<MentorSeminar | null>(null);
  const [completing, setCompleting] = useState<MentorSeminar | null>(null);
  const [now] = useState(() => Date.now());

  const upsert = (seminar: MentorSeminar) =>
    query.mutate((list) =>
      list.some((s) => s.id === seminar.id) ? list.map((s) => (s.id === seminar.id ? seminar : s)) : [seminar, ...list],
    );

  const open = (seminar: MentorSeminar | null) => {
    setEditing(seminar);
    setDialogOpen(true);
  };

  return (
    <section aria-labelledby="seminars-heading" className="mt-6 grid gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="seminars-heading" className="text-lg font-semibold">
            Group seminars
          </h2>
          <p className="text-sm text-muted-foreground">
            Run a session for several students at a fixed time. Students choose between one-to-one and your seminars
            when booking.
          </p>
        </div>
        <Button variant="outline" onClick={() => open(null)} disabled={!services.some((s) => s.is_active)}>
          <Plus aria-hidden="true" />
          Schedule seminar
        </Button>
      </div>
      <QueryView query={query} errorTitle="Couldn't load your seminars">
        {(seminars) =>
          seminars.length === 0 ? (
            <p className="rounded-xl border border-dashed p-5 text-sm text-muted-foreground">
              <Users className="mr-2 inline size-4" aria-hidden="true" />
              No seminars yet.
            </p>
          ) : (
            <ul className="grid grid-cols-1 gap-3">
              {seminars.map((seminar) => (
                <SeminarCard
                  key={seminar.id}
                  seminar={seminar}
                  now={now}
                  onEdit={() => open(seminar)}
                  onCancel={() => setCancelling(seminar)}
                  onComplete={() => setCompleting(seminar)}
                />
              ))}
            </ul>
          )
        }
      </QueryView>
      <SeminarDialog
        seminar={editing}
        services={services}
        minPrice={minPrice}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSaved={upsert}
      />
      <ConfirmationDialog
        open={cancelling !== null}
        onOpenChange={(isOpen) => !isOpen && setCancelling(null)}
        title="Cancel this seminar?"
        description="Every registered student is told and refunded in full. This can't be undone."
        confirmLabel="Cancel seminar"
        cancelLabel="Keep seminar"
        destructive
        reason={{ label: "Message to students", required: true }}
        onConfirm={async (reason) => {
          if (!cancelling) return;
          upsert(await api.mentor.cancelSeminar(cancelling.id, reason));
          toast.success("Seminar cancelled");
        }}
      />
      <ConfirmationDialog
        open={completing !== null}
        onOpenChange={(isOpen) => !isOpen && setCompleting(null)}
        title="Mark this seminar as completed?"
        description="Students who attended will be able to leave a review."
        confirmLabel="Mark completed"
        onConfirm={async () => {
          if (!completing) return;
          upsert(await api.mentor.completeSeminar(completing.id));
          toast.success("Seminar marked as completed");
        }}
      />
    </section>
  );
}
