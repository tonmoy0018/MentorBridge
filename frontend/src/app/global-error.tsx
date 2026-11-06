"use client";

/**
 * Last-resort error page for failures in the root layout. It replaces the whole document, so
 * it can't rely on the app's layout or styles.
 */
export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", padding: "4rem 1rem", textAlign: "center" }}>
        <h1>Something went wrong</h1>
        <p>MentorBridge couldn&apos;t load this page. Please try again in a moment.</p>
        <button type="button" onClick={reset} style={{ padding: "0.5rem 1rem", marginTop: "1rem" }}>
          Try again
        </button>
      </body>
    </html>
  );
}
