import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/errors";
import { ConfirmationDialog } from "@/components/feedback/confirmation-dialog";

describe("ConfirmationDialog", () => {
  it("requires a reason when configured and passes it to onConfirm", async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    const onOpenChange = vi.fn();
    render(
      <ConfirmationDialog
        open
        onOpenChange={onOpenChange}
        title="Decline request?"
        confirmLabel="Decline"
        reason={{ label: "Message to the student", required: true }}
        onConfirm={onConfirm}
      />,
    );
    const confirm = screen.getByRole("button", { name: "Decline" });
    expect(confirm).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/message to the student/i), "  Fully booked  ");
    await userEvent.click(confirm);
    expect(onConfirm).toHaveBeenCalledWith("Fully booked");
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("stays open and shows the error when the action fails", async () => {
    const onOpenChange = vi.fn();
    render(
      <ConfirmationDialog
        open
        onOpenChange={onOpenChange}
        title="Accept?"
        confirmLabel="Accept"
        onConfirm={() => Promise.reject(new ApiError({ kind: "conflict", status: 409, code: "invalid_state", message: "Already handled." }))}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Accept" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Already handled.");
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
  });
});
