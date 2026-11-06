"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Pencil, Plus, Target, Trash2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import type { CareerGoal, GoalInput, GoalStatus } from "@/lib/api/types";
import { api } from "@/lib/data/client";
import { formatCalendarDate } from "@/lib/format";
import { applyServerErrors } from "@/lib/forms";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { PageHeader } from "@/components/common/page-header";
import { QueryView } from "@/components/common/query-view";
import { ConfirmationDialog } from "@/components/feedback/confirmation-dialog";
import { EmptyState } from "@/components/feedback/empty-state";
import { FormAlert } from "@/components/forms/form-alert";
import { FormField } from "@/components/forms/form-field";
import { NativeSelect } from "@/components/forms/native-select";
import { useApiErrorHandler } from "@/hooks/use-api-error-handler";
import { useApiQuery } from "@/hooks/use-api-query";
import { GOAL_STATUS, GoalStatusBadge } from "./goal-status";

const goalSchema = z.object({
  title: z.string().trim().min(1, { error: "Give your goal a title." }).max(140, { error: "Keep the title under 140 characters." }),
  description: z.string().trim().max(1000, { error: "Keep the description under 1,000 characters." }),
  status: z.enum(["not_started", "in_progress", "achieved", "archived"]),
  target_date: z.string(),
});
type GoalValues = z.infer<typeof goalSchema>;

function GoalDialog({
  goal,
  open,
  onOpenChange,
  onSaved,
}: {
  goal: CareerGoal | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: (goal: CareerGoal) => void;
}) {
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<GoalValues>({
    resolver: zodResolver(goalSchema),
    values: {
      title: goal?.title ?? "",
      description: goal?.description ?? "",
      status: goal?.status ?? "not_started",
      target_date: goal?.target_date ?? "",
    },
  });

  async function onSubmit(values: GoalValues) {
    setFormError(null);
    const input: GoalInput = { ...values, target_date: values.target_date || null };
    try {
      const saved = goal ? await api.student.updateGoal(goal.id, input) : await api.student.createGoal(input);
      onSaved(saved);
      onOpenChange(false);
      toast.success(goal ? "Goal updated" : "Goal added");
    } catch (error) {
      setFormError(applyServerErrors(error, setError, ["title", "description", "status", "target_date"]));
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{goal ? "Edit goal" : "Add a goal"}</DialogTitle>
          <DialogDescription>Keep goals specific so you can share them with your mentors.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid grid-cols-1 gap-4">
          {formError ? <FormAlert>{formError}</FormAlert> : null}
          <FormField label="Goal" error={errors.title?.message} required>
            {(props) => <Input {...props} placeholder="e.g. Land a data analyst internship" {...register("title")} />}
          </FormField>
          <FormField label="Details" error={errors.description?.message}>
            {(props) => <Textarea {...props} rows={3} {...register("description")} />}
          </FormField>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField label="Status" error={errors.status?.message}>
              {(props) => (
                <NativeSelect {...props} {...register("status")}>
                  {(Object.keys(GOAL_STATUS) as GoalStatus[]).map((status) => (
                    <option key={status} value={status}>
                      {GOAL_STATUS[status].label}
                    </option>
                  ))}
                </NativeSelect>
              )}
            </FormField>
            <FormField label="Target date" error={errors.target_date?.message}>
              {(props) => <Input {...props} type="date" {...register("target_date")} />}
            </FormField>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Saving…" : goal ? "Save goal" : "Add goal"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function Goals() {
  const query = useApiQuery("student:goals", () => api.student.goals());
  const handleError = useApiErrorHandler();
  const [editing, setEditing] = useState<CareerGoal | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState<CareerGoal | null>(null);

  const upsert = (goal: CareerGoal) =>
    query.mutate((list) => (list.some((g) => g.id === goal.id) ? list.map((g) => (g.id === goal.id ? goal : g)) : [goal, ...list]));

  async function changeStatus(goal: CareerGoal, status: GoalStatus) {
    try {
      upsert(await api.student.updateGoal(goal.id, { status }));
    } catch (error) {
      handleError(error, "Couldn't update goal");
    }
  }

  function openDialog(goal: CareerGoal | null) {
    setEditing(goal);
    setDialogOpen(true);
  }

  return (
    <div className="grid grid-cols-1 gap-6">
      <PageHeader
        title="Career goals"
        description="Track what you're working towards and share it with your mentors."
        actions={
          <Button onClick={() => openDialog(null)}>
            <Plus aria-hidden="true" />
            Add goal
          </Button>
        }
      />
      <QueryView query={query} errorTitle="Couldn't load goals">
        {(goals) =>
          goals.length === 0 ? (
            <EmptyState
              icon={Target}
              title="No goals yet"
              description="Start with one concrete goal, like “Complete three mock interviews by June”."
              action={<Button onClick={() => openDialog(null)}>Add your first goal</Button>}
            />
          ) : (
            <ul className="grid grid-cols-1 gap-3">
              {goals.map((goal) => (
                <li key={goal.id} className="flex flex-col gap-4 rounded-xl border bg-card p-5 sm:flex-row sm:items-start">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="font-semibold">{goal.title}</h2>
                      <GoalStatusBadge status={goal.status} />
                    </div>
                    {goal.description ? <p className="mt-1 text-sm text-muted-foreground">{goal.description}</p> : null}
                    {goal.target_date ? (
                      <p className="mt-2 text-sm">Target date: {formatCalendarDate(goal.target_date)}</p>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <label className="sr-only" htmlFor={`status-${goal.id}`}>
                      Status for {goal.title}
                    </label>
                    <NativeSelect
                      id={`status-${goal.id}`}
                      value={goal.status}
                      onChange={(e) => changeStatus(goal, e.target.value as GoalStatus)}
                      className="h-8 w-36 text-sm"
                    >
                      {(Object.keys(GOAL_STATUS) as GoalStatus[]).map((status) => (
                        <option key={status} value={status}>
                          {GOAL_STATUS[status].label}
                        </option>
                      ))}
                    </NativeSelect>
                    <Button size="icon-sm" variant="ghost" onClick={() => openDialog(goal)} aria-label={`Edit ${goal.title}`}>
                      <Pencil aria-hidden="true" />
                    </Button>
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      className="text-destructive"
                      onClick={() => setDeleting(goal)}
                      aria-label={`Delete ${goal.title}`}
                    >
                      <Trash2 aria-hidden="true" />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )
        }
      </QueryView>

      <GoalDialog goal={editing} open={dialogOpen} onOpenChange={setDialogOpen} onSaved={upsert} />
      <ConfirmationDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete this goal?"
        description={deleting ? `“${deleting.title}” will be removed permanently.` : undefined}
        confirmLabel="Delete goal"
        destructive
        onConfirm={async () => {
          if (!deleting) return;
          await api.student.deleteGoal(deleting.id);
          query.mutate((list) => list.filter((g) => g.id !== deleting.id));
          toast.success("Goal deleted");
        }}
      />
    </div>
  );
}
