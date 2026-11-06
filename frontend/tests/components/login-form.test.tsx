import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/errors";

const replace = vi.fn();
const refresh = vi.fn();
let search = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, refresh, push: vi.fn() }),
  useSearchParams: () => search,
  usePathname: () => "/login",
}));

const login = vi.fn();
vi.mock("@/lib/data/client", () => ({ api: { auth: { login: (...args: unknown[]) => login(...args) } } }));

const { LoginForm } = await import("@/components/auth/login-form");

describe("LoginForm", () => {
  beforeEach(() => {
    replace.mockReset();
    login.mockReset();
    search = new URLSearchParams();
  });

  it("shows accessible validation errors without calling the API", async () => {
    render(<LoginForm />);
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));

    const email = screen.getByLabelText(/email/i);
    expect(email).toHaveAttribute("aria-invalid", "true");
    expect(email).toHaveAccessibleDescription(/enter your email address/i);
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });

  it("logs in and redirects to a safe ?next path", async () => {
    search = new URLSearchParams({ next: "/dashboard/student/goals" });
    login.mockResolvedValue({ role: "student" });
    render(<LoginForm />);
    await userEvent.type(screen.getByLabelText(/email/i), "jordan@example.com");
    await userEvent.type(screen.getByLabelText(/^password/i), "correct horse");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard/student/goals"));
    expect(login).toHaveBeenCalledWith({ email: "jordan@example.com", password: "correct horse" });
  });

  it("ignores an external ?next and falls back to the role dashboard", async () => {
    search = new URLSearchParams({ next: "https://evil.example" });
    login.mockResolvedValue({ role: "mentor" });
    render(<LoginForm />);
    await userEvent.type(screen.getByLabelText(/email/i), "amara@example.com");
    await userEvent.type(screen.getByLabelText(/^password/i), "secret-pass");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard/mentor"));
  });

  it("shows a generic message for invalid credentials", async () => {
    login.mockRejectedValue(
      new ApiError({ kind: "validation", status: 400, code: "invalid_credentials", message: "Email or password is incorrect." }),
    );
    render(<LoginForm />);
    await userEvent.type(screen.getByLabelText(/email/i), "nobody@example.com");
    await userEvent.type(screen.getByLabelText(/^password/i), "wrong-pass");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Email or password is incorrect.");
    expect(replace).not.toHaveBeenCalled();
  });

  it("explains an expired session", () => {
    search = new URLSearchParams({ reason: "expired" });
    render(<LoginForm />);
    expect(screen.getByText(/please log in again/i)).toBeInTheDocument();
  });
});
