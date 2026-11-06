/**
 * Hands the browser to the payment provider's hosted checkout. Card details are entered only on
 * the provider's page, never in MentorBridge. Only https URLs are followed.
 */
export function goToCheckout(url: string): void {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    throw new Error("The payment page address is invalid. Please try again.");
  }
  if (parsed.protocol !== "https:") throw new Error("The payment page address is invalid. Please try again.");
  window.location.assign(parsed.toString());
}
