"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import type { AvailabilityRule, MentorOwnProfile } from "@/lib/api/types";
import { api } from "@/lib/data/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { PageHeader } from "@/components/common/page-header";
import { ErrorState } from "@/components/feedback/error-state";
import { LoadingState } from "@/components/feedback/loading-state";
import { FormField } from "@/components/forms/form-field";
import { NativeSelect } from "@/components/forms/native-select";
import { useApiErrorHandler } from "@/hooks/use-api-error-handler";
import { useApiQuery } from "@/hooks/use-api-query";

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

type Range = { start_time: string; end_time: string };
type Week = Range[][];

function toWeek(rules: AvailabilityRule[]): Week {
  const week: Week = WEEKDAYS.map(() => []);
  for (const rule of rules) week[rule.weekday]!.push({ start_time: rule.start_time, end_time: rule.end_time });
  for (const day of week) day.sort((a, b) => a.start_time.localeCompare(b.start_time));
  return week;
}

/** Returns an error message for a day's ranges, or null if they are valid. */
export function validateDay(ranges: Range[]): string | null {
  const sorted = [...ranges].sort((a, b) => a.start_time.localeCompare(b.start_time));
  for (const range of sorted) {
    if (!range.start_time || !range.end_time) return "Enter a start and end time.";
    if (range.end_time <= range.start_time) return "End time must be after start time.";
  }
  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i]!.start_time < sorted[i - 1]!.end_time) return "Time ranges can't overlap.";
  }
  return null;
}

function WeeklyHours({ initial, timezone }: { initial: AvailabilityRule[]; timezone: string }) {
  const handleError = useApiErrorHandler();
  const [week, setWeek] = useState<Week>(() => toWeek(initial));
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const errors = week.map(validateDay);
  const hasErrors = errors.some(Boolean);

  const update = (fn: (draft: Week) => void) => {
    setWeek((current) => {
      const draft = current.map((day) => day.map((r) => ({ ...r })));
      fn(draft);
      return draft;
    });
    setDirty(true);
  };

  async function save() {
    if (hasErrors) return;
    setSaving(true);
    try {
      const rules = week.flatMap((ranges, weekday) => ranges.map((r) => ({ weekday, ...r })));
      setWeek(toWeek(await api.mentor.replaceAvailabilityRules(rules)));
      setDirty(false);
      toast.success("Weekly hours saved");
    } catch (error) {
      handleError(error, "Couldn't save your hours");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section aria-labelledby="weekly-heading" className="rounded-xl border bg-card p-6">
      <h2 id="weekly-heading" className="text-lg font-semibold">
        Weekly hours
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Times are in your profile time zone: <span className="font-medium text-foreground">{timezone.replace(/_/g, " ")}</span>.
        Students see them converted to their own time zone.
      </p>
      <ul className="mt-5 divide-y">
        {week.map((ranges, weekday) => {
          const dayName = WEEKDAYS[weekday]!;
          const error = errors[weekday];
          return (
            <li key={dayName} className="grid grid-cols-1 gap-3 py-4 sm:grid-cols-[10rem_1fr]">
              <label className="flex items-center gap-3 text-sm font-medium">
                <Switch
                  checked={ranges.length > 0}
                  onCheckedChange={(on) =>
                    update((draft) => {
                      draft[weekday] = on ? [{ start_time: "09:00", end_time: "17:00" }] : [];
                    })
                  }
                  aria-label={`Available on ${dayName}`}
                />
                {dayName}
              </label>
              <div className="grid grid-cols-1 gap-2">
                {ranges.length === 0 ? (
                  <p className="py-2 text-sm text-muted-foreground">Unavailable</p>
                ) : (
                  ranges.map((range, index) => (
                    <div key={index} className="flex flex-wrap items-center gap-2">
                      <label className="sr-only" htmlFor={`start-${weekday}-${index}`}>
                        {dayName} start time {index + 1}
                      </label>
                      <Input
                        id={`start-${weekday}-${index}`}
                        type="time"
                        step={900}
                        value={range.start_time}
                        onChange={(e) => update((d) => void (d[weekday]![index]!.start_time = e.target.value))}
                        className="w-32"
                        aria-invalid={error ? true : undefined}
                      />
                      <span aria-hidden="true">–</span>
                      <label className="sr-only" htmlFor={`end-${weekday}-${index}`}>
                        {dayName} end time {index + 1}
                      </label>
                      <Input
                        id={`end-${weekday}-${index}`}
                        type="time"
                        step={900}
                        value={range.end_time}
                        onChange={(e) => update((d) => void (d[weekday]![index]!.end_time = e.target.value))}
                        className="w-32"
                        aria-invalid={error ? true : undefined}
                      />
                      <Button
                        size="icon-sm"
                        variant="ghost"
                        onClick={() => update((d) => void d[weekday]!.splice(index, 1))}
                        aria-label={`Remove ${dayName} hours ${range.start_time}–${range.end_time}`}
                      >
                        <Trash2 aria-hidden="true" />
                      </Button>
                    </div>
                  ))
                )}
                {ranges.length > 0 ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-fit"
                    onClick={() =>
                      update((d) => {
                        const last = d[weekday]!.at(-1)!;
                        const start = last.end_time < "22:00" ? last.end_time : "18:00";
                        const [h, m] = start.split(":").map(Number);
                        const end = `${String(Math.min((h ?? 18) + 1, 23)).padStart(2, "0")}:${String(m ?? 0).padStart(2, "0")}`;
                        d[weekday]!.push({ start_time: start, end_time: end });
                      })
                    }
                  >
                    <Plus aria-hidden="true" />
                    Add hours
                  </Button>
                ) : null}
                {error ? (
                  <p role="alert" className="text-sm text-destructive">
                    {error}
                  </p>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
      <div className="mt-4 flex items-center gap-3 border-t pt-4">
        <Button onClick={save} disabled={saving || hasErrors || !dirty}>
          {saving ? "Saving…" : "Save weekly hours"}
        </Button>
        {hasErrors ? <span className="text-sm text-destructive">Fix the highlighted days to save.</span> : null}
      </div>
    </section>
  );
}

const NOTICE = [2, 12, 24, 48, 72];
const HORIZON = [14, 30, 60, 90];
const BUFFER = [0, 10, 15, 30];

function BookingSettings({ profile, onSaved }: { profile: MentorOwnProfile; onSaved: (p: MentorOwnProfile) => void }) {
  const handleError = useApiErrorHandler();
  const [values, setValues] = useState({
    is_accepting_bookings: profile.is_accepting_bookings,
    auto_accept: profile.auto_accept,
    min_notice_hours: profile.min_notice_hours,
    booking_horizon_days: profile.booking_horizon_days,
    buffer_minutes: profile.buffer_minutes,
  });
  const [saving, setSaving] = useState(false);
  const set = <K extends keyof typeof values>(key: K, value: (typeof values)[K]) => setValues((v) => ({ ...v, [key]: value }));

  async function save() {
    setSaving(true);
    try {
      onSaved(await api.mentor.updateProfile(values));
      toast.success("Booking settings saved");
    } catch (error) {
      handleError(error, "Couldn't save booking settings");
    } finally {
      setSaving(false);
    }
  }

  const withCurrent = (options: number[], current: number) => [...new Set([...options, current])].sort((a, b) => a - b);

  return (
    <section aria-labelledby="settings-heading" className="rounded-xl border bg-card p-6">
      <h2 id="settings-heading" className="text-lg font-semibold">
        Booking settings
      </h2>
      <div className="mt-5 grid gap-5">
        <label className="flex items-start gap-3">
          <Switch
            checked={values.is_accepting_bookings}
            onCheckedChange={(v) => set("is_accepting_bookings", v)}
            className="mt-0.5"
          />
          <span>
            <span className="block text-sm font-medium">Accepting new bookings</span>
            <span className="block text-sm text-muted-foreground">Turn off to pause new requests. Existing bookings are not affected.</span>
          </span>
        </label>
        <label className="flex items-start gap-3">
          <Switch checked={values.auto_accept} onCheckedChange={(v) => set("auto_accept", v)} className="mt-0.5" />
          <span>
            <span className="block text-sm font-medium">Accept requests automatically</span>
            <span className="block text-sm text-muted-foreground">Requests within your hours are confirmed without review.</span>
          </span>
        </label>
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
          <FormField label="Minimum notice">
            {(props) => (
              <NativeSelect {...props} value={values.min_notice_hours} onChange={(e) => set("min_notice_hours", Number(e.target.value))}>
                {withCurrent(NOTICE, values.min_notice_hours).map((h) => (
                  <option key={h} value={h}>
                    {h} hours
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
          <FormField label="Book up to">
            {(props) => (
              <NativeSelect {...props} value={values.booking_horizon_days} onChange={(e) => set("booking_horizon_days", Number(e.target.value))}>
                {withCurrent(HORIZON, values.booking_horizon_days).map((d) => (
                  <option key={d} value={d}>
                    {d} days ahead
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
          <FormField label="Break between sessions">
            {(props) => (
              <NativeSelect {...props} value={values.buffer_minutes} onChange={(e) => set("buffer_minutes", Number(e.target.value))}>
                {withCurrent(BUFFER, values.buffer_minutes).map((m) => (
                  <option key={m} value={m}>
                    {m === 0 ? "No break" : `${m} minutes`}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
        </div>
        <div>
          <Button onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Save settings"}
          </Button>
        </div>
      </div>
    </section>
  );
}

export function AvailabilityEditor() {
  const rules = useApiQuery("mentor:rules", () => api.mentor.availabilityRules());
  const profile = useApiQuery("mentor:profile", () => api.mentor.profile());

  return (
    <div className="grid grid-cols-1 gap-6">
      <PageHeader title="Availability" description="Set when students can book you. Bookings never overlap." />
      {rules.status === "error" || profile.status === "error" ? (
        <ErrorState
          error={rules.error ?? profile.error}
          title="Couldn't load your availability"
          onRetry={() => {
            rules.reload();
            profile.reload();
          }}
        />
      ) : !rules.data || !profile.data ? (
        <LoadingState label="Loading availability…" />
      ) : (
        <>
          <WeeklyHours initial={rules.data} timezone={profile.data.timezone} />
          <BookingSettings profile={profile.data} onSaved={(p) => profile.mutate(() => p)} />
        </>
      )}
    </div>
  );
}
