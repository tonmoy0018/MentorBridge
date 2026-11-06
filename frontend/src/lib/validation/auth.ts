import { z } from "zod";

/**
 * Client-side validation for fast, accessible feedback. The Django API re-validates
 * everything (including its password strength validators) and is authoritative.
 */
export const emailField = z
  .string()
  .trim()
  .min(1, { error: "Enter your email address." })
  .max(254, { error: "Email address is too long." })
  .pipe(z.email({ error: "Enter a valid email address, like name@example.com." }));

export const newPasswordField = z
  .string()
  .min(8, { error: "Use at least 8 characters." })
  .max(128, { error: "Use 128 characters or fewer." })
  .refine((value) => !/^\d+$/.test(value), { error: "Your password can't be entirely numeric." });

const nameField = (label: string) =>
  z
    .string()
    .trim()
    .min(1, { error: `Enter your ${label}.` })
    .max(80, { error: `Your ${label} must be 80 characters or fewer.` });

export const loginSchema = z.object({
  email: emailField,
  password: z.string().min(1, { error: "Enter your password." }),
});
export type LoginValues = z.infer<typeof loginSchema>;

export const signupSchema = z
  .object({
    first_name: nameField("first name"),
    last_name: nameField("last name"),
    email: emailField,
    password: newPasswordField,
    confirm_password: z.string().min(1, { error: "Confirm your password." }),
  })
  .refine((v) => v.password === v.confirm_password, {
    path: ["confirm_password"],
    error: "Passwords don't match.",
  });
export type SignupValues = z.infer<typeof signupSchema>;

export const forgotPasswordSchema = z.object({ email: emailField });
export type ForgotPasswordValues = z.infer<typeof forgotPasswordSchema>;

export const resetPasswordSchema = z
  .object({
    new_password: newPasswordField,
    confirm_password: z.string().min(1, { error: "Confirm your new password." }),
  })
  .refine((v) => v.new_password === v.confirm_password, {
    path: ["confirm_password"],
    error: "Passwords don't match.",
  });
export type ResetPasswordValues = z.infer<typeof resetPasswordSchema>;

export const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, { error: "Enter your current password." }),
    new_password: newPasswordField,
    confirm_password: z.string().min(1, { error: "Confirm your new password." }),
  })
  .refine((v) => v.new_password === v.confirm_password, {
    path: ["confirm_password"],
    error: "Passwords don't match.",
  })
  .refine((v) => v.new_password !== v.current_password, {
    path: ["new_password"],
    error: "Choose a password different from your current one.",
  });
export type ChangePasswordValues = z.infer<typeof changePasswordSchema>;
