import { initials } from "@/lib/format";
import { cn } from "@/lib/utils";

const SIZES = {
  sm: "size-9 text-xs",
  md: "size-12 text-sm",
  lg: "size-16 text-lg",
  xl: "size-24 text-2xl sm:size-28 sm:text-3xl",
} as const;

/**
 * Profile photo with an initials placeholder when no photo is available.
 * Uses a plain <img> because avatars come from user uploads on the API/media host.
 */
export function MentorAvatar({
  name,
  src,
  size = "md",
  className,
}: {
  name: string;
  src: string | null;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-secondary font-semibold text-secondary-foreground ring-1 ring-border",
        SIZES[size],
        className,
      )}
    >
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt={`Photo of ${name}`} className="size-full object-cover" loading="lazy" />
      ) : (
        <span aria-hidden="true">{initials(name)}</span>
      )}
    </span>
  );
}
