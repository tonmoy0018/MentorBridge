"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ExternalLink, Pencil, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useForm, useWatch, type UseFormRegister } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import type { CountryCode, MentorExperience, MentorOwnProfile, Taxonomy } from "@/lib/api/types";
import { api } from "@/lib/data/client";
import { formatMonthYear } from "@/lib/format";
import { applyServerErrors } from "@/lib/forms";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { PageHeader } from "@/components/common/page-header";
import { ConfirmationDialog } from "@/components/feedback/confirmation-dialog";
import { ErrorState } from "@/components/feedback/error-state";
import { LoadingState } from "@/components/feedback/loading-state";
import { FormAlert } from "@/components/forms/form-alert";
import { FormField, FormFieldset } from "@/components/forms/form-field";
import { NativeSelect } from "@/components/forms/native-select";
import { useTimeZones } from "@/features/account/account-settings";
import { useApiQuery } from "@/hooks/use-api-query";
import { VerificationNotice } from "./verification-status";

const optionalUrl = (check: (url: URL) => boolean, message: string) =>
  z
    .string()
    .trim()
    .refine((value) => {
      if (!value) return true;
      try {
        return check(new URL(value));
      } catch {
        return false;
      }
    }, { error: message });

const profileSchema = z.object({
  headline: z.string().trim().min(10, { error: "Write a headline of at least 10 characters." }).max(140),
  current_title: z.string().trim().min(1, { error: "Enter your current job title." }).max(120),
  current_company: z.string().trim().max(120),
  profession_id: z.string().min(1, { error: "Choose your profession." }),
  years_experience: z
    .number({ error: "Enter your years of experience." })
    .int()
    .min(0, { error: "Enter 0 or more." })
    .max(60, { error: "Enter 60 or fewer." }),
  country: z.string().min(1, { error: "Choose your country." }),
  city: z.string().trim().max(100, { error: "Keep this under 100 characters." }),
  timezone: z.string().min(1),
  linkedin_url: optionalUrl(
    (u) => u.protocol === "https:" && /(^|\.)linkedin\.com$/.test(u.hostname),
    "Enter a LinkedIn profile URL starting with https://",
  ),
  meeting_url: optionalUrl((u) => u.protocol === "https:", "Enter a secure (https://) meeting link."),
  bio: z
    .string()
    .trim()
    .min(50, { error: "Write at least 50 characters so students know how you can help." })
    .max(2000, { error: "Keep your bio under 2,000 characters." }),
  industry_ids: z.array(z.string()).min(1, { error: "Choose at least one industry." }).max(3, { error: "Choose up to 3 industries." }),
  skill_ids: z.array(z.string()).min(1, { error: "Choose at least one skill." }).max(10, { error: "Choose up to 10 skills." }),
  language_codes: z.array(z.string()).min(1, { error: "Choose at least one language." }),
});
type ProfileValues = z.infer<typeof profileSchema>;

function CheckboxGrid({
  name,
  options,
  register,
}: {
  name: "industry_ids" | "skill_ids" | "language_codes";
  options: { value: string; label: string }[];
  register: UseFormRegister<ProfileValues>;
}) {
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {options.map((option) => (
        <label key={option.value} className="flex items-center gap-2 text-sm">
          <input type="checkbox" value={option.value} className="size-4 accent-primary" {...register(name)} />
          {option.label}
        </label>
      ))}
    </div>
  );
}

function ProfileForm({
  profile,
  taxonomy,
  onSaved,
}: {
  profile: MentorOwnProfile;
  taxonomy: Taxonomy;
  onSaved: (profile: MentorOwnProfile) => void;
}) {
  const zones = useTimeZones(profile.timezone);
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      headline: profile.headline,
      current_title: profile.current_title,
      current_company: profile.current_company,
      profession_id: profile.profession_id ? String(profile.profession_id) : "",
      years_experience: profile.years_experience,
      country: profile.country ?? "",
      city: profile.city,
      timezone: profile.timezone,
      linkedin_url: profile.linkedin_url,
      meeting_url: profile.meeting_url,
      bio: profile.bio,
      industry_ids: profile.industry_ids.map(String),
      skill_ids: profile.skill_ids.map(String),
      language_codes: profile.language_codes,
    },
  });

  async function onSubmit(values: ProfileValues) {
    setFormError(null);
    try {
      const updated = await api.mentor.updateProfile({
        ...values,
        // The select only offers codes from the backend's country list.
        country: values.country as CountryCode,
        profession_id: Number(values.profession_id),
        industry_ids: values.industry_ids.map(Number),
        skill_ids: values.skill_ids.map(Number),
      });
      onSaved(updated);
      reset(values);
      toast.success("Profile saved");
    } catch (error) {
      setFormError(applyServerErrors(error, setError, Object.keys(profileSchema.shape) as (keyof ProfileValues)[]));
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid grid-cols-1 gap-6">
      {formError ? <FormAlert>{formError}</FormAlert> : null}

      <section aria-labelledby="basics-heading" className="grid grid-cols-1 gap-5 rounded-xl border bg-card p-6">
        <h2 id="basics-heading" className="text-lg font-semibold">
          Professional details
        </h2>
        <FormField
          label="Headline"
          error={errors.headline?.message}
          description="One line shown on your card, e.g. “Senior PM helping career switchers break into product”."
          required
        >
          {(props) => <Input {...props} maxLength={140} {...register("headline")} />}
        </FormField>
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <FormField label="Current job title" error={errors.current_title?.message} required>
            {(props) => <Input {...props} {...register("current_title")} />}
          </FormField>
          <FormField label="Company" error={errors.current_company?.message}>
            {(props) => <Input {...props} {...register("current_company")} />}
          </FormField>
          <FormField label="Profession" error={errors.profession_id?.message} required>
            {(props) => (
              <NativeSelect {...props} {...register("profession_id")}>
                <option value="">Choose a profession</option>
                {taxonomy.professions.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
          <FormField label="Years of experience" error={errors.years_experience?.message} required>
            {(props) => (
              <Input {...props} type="number" inputMode="numeric" min={0} max={60} {...register("years_experience", { valueAsNumber: true })} />
            )}
          </FormField>
          <FormField label="Country" error={errors.country?.message} required>
            {(props) => (
              <NativeSelect {...props} {...register("country")}>
                <option value="">Choose a country</option>
                {taxonomy.countries.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.name}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
          <FormField label="City or region" error={errors.city?.message} description="Optional, shown on your profile.">
            {(props) => <Input {...props} {...register("city")} />}
          </FormField>
          <FormField label="Time zone" error={errors.timezone?.message} description="Your availability is set in this time zone." required>
            {(props) => (
              <NativeSelect {...props} {...register("timezone")}>
                {zones.map((zone) => (
                  <option key={zone} value={zone}>
                    {zone.replace(/_/g, " ")}
                  </option>
                ))}
              </NativeSelect>
            )}
          </FormField>
        </div>
        <FormField
          label="About you"
          error={errors.bio?.message}
          description="Your background, who you help and what a session with you looks like."
          required
        >
          {(props) => <Textarea {...props} rows={7} {...register("bio")} />}
        </FormField>
      </section>

      <section aria-labelledby="expertise-heading" className="grid grid-cols-1 gap-6 rounded-xl border bg-card p-6">
        <h2 id="expertise-heading" className="text-lg font-semibold">
          Expertise
        </h2>
        <FormFieldset legend="Industries" description="Up to 3." error={errors.industry_ids?.message}>
          <CheckboxGrid
            name="industry_ids"
            register={register}
            options={taxonomy.industries.map((i) => ({ value: String(i.id), label: i.name }))}
          />
        </FormFieldset>
        <FormFieldset legend="Skills" description="Up to 10." error={errors.skill_ids?.message}>
          <CheckboxGrid
            name="skill_ids"
            register={register}
            options={taxonomy.skills.map((s) => ({ value: String(s.id), label: s.name }))}
          />
        </FormFieldset>
        <FormFieldset legend="Languages you mentor in" error={errors.language_codes?.message}>
          <CheckboxGrid
            name="language_codes"
            register={register}
            options={taxonomy.languages.map((l) => ({ value: l.code, label: l.name }))}
          />
        </FormFieldset>
      </section>

      <section aria-labelledby="links-heading" className="grid grid-cols-1 gap-5 rounded-xl border bg-card p-6">
        <h2 id="links-heading" className="text-lg font-semibold">
          Links
        </h2>
        <FormField
          label="LinkedIn profile"
          error={errors.linkedin_url?.message}
          description="Helps our team verify your experience. Not shown publicly."
        >
          {(props) => <Input {...props} type="url" placeholder="https://www.linkedin.com/in/…" {...register("linkedin_url")} />}
        </FormField>
        <FormField
          label="Default meeting link"
          error={errors.meeting_url?.message}
          description="Shared with students only after you accept their booking."
        >
          {(props) => <Input {...props} type="url" placeholder="https://" {...register("meeting_url")} />}
        </FormField>
      </section>

      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" size="lg" disabled={isSubmitting || !isDirty}>
          {isSubmitting ? "Saving…" : "Save profile"}
        </Button>
        {!isDirty ? <span className="text-sm text-muted-foreground">No unsaved changes</span> : null}
      </div>
    </form>
  );
}

const experienceSchema = z
  .object({
    kind: z.enum(["work", "education"]),
    title: z.string().trim().min(1, { error: "Enter a role or qualification." }).max(120),
    organization: z.string().trim().min(1, { error: "Enter the organisation." }).max(120),
    start_date: z.string().min(1, { error: "Enter a start date." }),
    end_date: z.string(),
    current: z.boolean(),
    description: z.string().trim().max(500, { error: "Keep this under 500 characters." }),
  })
  .refine((v) => v.current || !v.end_date || v.end_date >= v.start_date, {
    path: ["end_date"],
    error: "End date must be after the start date.",
  });
type ExperienceValues = z.infer<typeof experienceSchema>;

function ExperienceDialog({
  experience,
  open,
  onOpenChange,
  onSaved,
}: {
  experience: MentorExperience | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: (experience: MentorExperience) => void;
}) {
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    control,
    formState: { errors, isSubmitting },
  } = useForm<ExperienceValues>({
    resolver: zodResolver(experienceSchema),
    values: {
      kind: experience?.kind ?? "work",
      title: experience?.title ?? "",
      organization: experience?.organization ?? "",
      start_date: experience?.start_date ?? "",
      end_date: experience?.end_date ?? "",
      current: experience ? experience.end_date === null : false,
      description: experience?.description ?? "",
    },
  });
  const current = useWatch({ control, name: "current" });

  async function onSubmit({ current: isCurrent, ...values }: ExperienceValues) {
    setFormError(null);
    const input = { ...values, end_date: isCurrent || !values.end_date ? null : values.end_date };
    try {
      const saved = experience
        ? await api.mentor.updateExperience(experience.id, input)
        : await api.mentor.createExperience(input);
      onSaved(saved);
      onOpenChange(false);
      toast.success(experience ? "Experience updated" : "Experience added");
    } catch (error) {
      setFormError(applyServerErrors(error, setError, ["title", "organization", "start_date", "end_date", "description"]));
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{experience ? "Edit experience" : "Add experience"}</DialogTitle>
          <DialogDescription>Work history and education shown on your public profile.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid grid-cols-1 gap-4">
          {formError ? <FormAlert>{formError}</FormAlert> : null}
          <FormFieldset legend="Type">
            <div className="flex gap-4">
              {(["work", "education"] as const).map((kind) => (
                <label key={kind} className="flex items-center gap-2 text-sm">
                  <input type="radio" value={kind} className="size-4 accent-primary" {...register("kind")} />
                  {kind === "work" ? "Work" : "Education"}
                </label>
              ))}
            </div>
          </FormFieldset>
          <FormField label="Role or qualification" error={errors.title?.message} required>
            {(props) => <Input {...props} {...register("title")} />}
          </FormField>
          <FormField label="Organisation" error={errors.organization?.message} required>
            {(props) => <Input {...props} {...register("organization")} />}
          </FormField>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField label="Start date" error={errors.start_date?.message} required>
              {(props) => <Input {...props} type="date" {...register("start_date")} />}
            </FormField>
            <FormField label="End date" error={errors.end_date?.message}>
              {(props) => <Input {...props} type="date" disabled={current} {...register("end_date")} />}
            </FormField>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4 accent-primary" {...register("current")} />I currently work or study here
          </label>
          <FormField label="Description" error={errors.description?.message}>
            {(props) => <Textarea {...props} rows={3} {...register("description")} />}
          </FormField>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ExperienceManager({ initial }: { initial: MentorExperience[] }) {
  const [items, setItems] = useState(initial);
  const [editing, setEditing] = useState<MentorExperience | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState<MentorExperience | null>(null);

  const sorted = [...items].sort((a, b) => b.start_date.localeCompare(a.start_date));
  const open = (experience: MentorExperience | null) => {
    setEditing(experience);
    setDialogOpen(true);
  };

  return (
    <section aria-labelledby="experience-heading" className="grid grid-cols-1 gap-4 rounded-xl border bg-card p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="experience-heading" className="text-lg font-semibold">
          Experience & education
        </h2>
        <Button variant="outline" size="sm" onClick={() => open(null)}>
          <Plus aria-hidden="true" />
          Add
        </Button>
      </div>
      {sorted.length === 0 ? (
        <p className="text-sm text-muted-foreground">Add your roles and education so students understand your background.</p>
      ) : (
        <ul className="divide-y">
          {sorted.map((experience) => (
            <li key={experience.id} className="flex items-start justify-between gap-3 py-3">
              <div className="min-w-0">
                <p className="font-medium">{experience.title}</p>
                <p className="text-sm text-muted-foreground">
                  {experience.organization} · {formatMonthYear(experience.start_date)} –{" "}
                  {experience.end_date ? formatMonthYear(experience.end_date) : "Present"}
                </p>
              </div>
              <div className="flex shrink-0 gap-1">
                <Button size="icon-sm" variant="ghost" onClick={() => open(experience)} aria-label={`Edit ${experience.title}`}>
                  <Pencil aria-hidden="true" />
                </Button>
                <Button
                  size="icon-sm"
                  variant="ghost"
                  className="text-destructive"
                  onClick={() => setDeleting(experience)}
                  aria-label={`Delete ${experience.title}`}
                >
                  <Trash2 aria-hidden="true" />
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <ExperienceDialog
        experience={editing}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSaved={(saved) =>
          setItems((list) => (list.some((e) => e.id === saved.id) ? list.map((e) => (e.id === saved.id ? saved : e)) : [...list, saved]))
        }
      />
      <ConfirmationDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
        title="Remove this entry?"
        description={deleting ? `${deleting.title} at ${deleting.organization} will be removed from your profile.` : undefined}
        confirmLabel="Remove"
        destructive
        onConfirm={async () => {
          if (!deleting) return;
          await api.mentor.deleteExperience(deleting.id);
          setItems((list) => list.filter((e) => e.id !== deleting.id));
          toast.success("Entry removed");
        }}
      />
    </section>
  );
}

export function MentorProfileEditor() {
  const profile = useApiQuery("mentor:profile", () => api.mentor.profile());
  const taxonomy = useApiQuery("taxonomy", () => api.taxonomy.get());
  const [submitOpen, setSubmitOpen] = useState(false);

  if (profile.status === "error" || taxonomy.status === "error") {
    return (
      <ErrorState
        error={profile.error ?? taxonomy.error}
        title="Couldn't load your profile"
        onRetry={() => {
          profile.reload();
          taxonomy.reload();
        }}
      />
    );
  }
  if (!profile.data || !taxonomy.data) return <LoadingState label="Loading your profile…" />;

  const data = profile.data;
  const canSubmit = data.verification_status === "draft" || data.verification_status === "rejected";

  return (
    <div className="grid grid-cols-1 gap-6">
      <PageHeader
        title="Your profile"
        description="This is what students see when they find you."
        actions={
          data.verification_status === "approved" ? (
            <Button asChild variant="outline">
              <Link href={`/mentors/${data.slug}`} target="_blank" rel="noopener noreferrer">
                View public profile <ExternalLink aria-hidden="true" />
                <span className="sr-only">(opens in a new tab)</span>
              </Link>
            </Button>
          ) : undefined
        }
      />

      <VerificationNotice
        status={data.verification_status}
        reason={data.verification_decision_reason}
        action={canSubmit ? <Button onClick={() => setSubmitOpen(true)}>Submit for review</Button> : undefined}
      />

      <ProfileForm profile={data} taxonomy={taxonomy.data} onSaved={(p) => profile.mutate(() => p)} />
      <ExperienceManager initial={data.experiences} />

      <ConfirmationDialog
        open={submitOpen}
        onOpenChange={setSubmitOpen}
        title="Submit your profile for review?"
        description="Make sure you've saved your latest changes. Our team will check your details and email you with a decision."
        confirmLabel="Submit for review"
        reason={{
          label: "Notes for the reviewer",
          placeholder: "Anything that helps verify your experience, e.g. how to confirm your current role.",
        }}
        onConfirm={async (note) => {
          const updated = await api.mentor.submitVerification(note);
          profile.mutate(() => updated);
          toast.success("Profile submitted for review");
        }}
      />
    </div>
  );
}
