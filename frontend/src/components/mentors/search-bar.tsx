import { Search } from "lucide-react";
import Form from "next/form";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/**
 * Mentor search. A GET form to /mentors: works without JavaScript, and next/form turns it
 * into a client-side navigation when JavaScript is available.
 */
export function SearchBar({
  defaultValue,
  size = "default",
  hiddenParams,
  className,
  autoFocus,
}: {
  defaultValue?: string;
  size?: "default" | "lg";
  /** Other active params to preserve when searching (e.g. filters on /mentors). */
  hiddenParams?: Record<string, string | number | undefined>;
  className?: string;
  autoFocus?: boolean;
}) {
  const large = size === "lg";
  return (
    <Form action="/mentors" role="search" aria-label="Search mentors" className={cn("flex w-full gap-2", className)}>
      {hiddenParams
        ? Object.entries(hiddenParams).map(([key, value]) =>
            value === undefined || value === "" ? null : (
              <input key={key} type="hidden" name={key} value={String(value)} />
            ),
          )
        : null}
      <div className="relative flex-1">
        <Search
          className={cn(
            "pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted-foreground",
            large ? "size-5" : "size-4",
          )}
          aria-hidden="true"
        />
        <label htmlFor={large ? "hero-search" : "mentor-search"} className="sr-only">
          Search by mentor, profession, skill or industry
        </label>
        <Input
          id={large ? "hero-search" : "mentor-search"}
          type="search"
          name="q"
          defaultValue={defaultValue}
          placeholder={large ? "Try “product manager”, “SQL” or “finance”" : "Search mentors, professions, skills…"}
          maxLength={100}
          autoComplete="off"
          autoFocus={autoFocus}
          className={cn(large ? "h-12 pl-10 text-base md:text-base" : "pl-9")}
        />
      </div>
      <Button type="submit" size={large ? "lg" : "default"} className={cn(large && "h-12")}>
        Search
      </Button>
    </Form>
  );
}
