"use client";

import { SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import type { MentorSearchParams, Taxonomy } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { MentorFilters } from "./mentor-filters";

export function MobileFilters({
  taxonomy,
  params,
  activeCount,
}: {
  taxonomy: Taxonomy;
  params: MentorSearchParams;
  activeCount: number;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="outline" className="lg:hidden">
          <SlidersHorizontal aria-hidden="true" />
          Filters
          {activeCount > 0 ? (
            <span className="rounded-full bg-primary px-1.5 text-xs text-primary-foreground">
              <span className="sr-only">(</span>
              {activeCount}
              <span className="sr-only"> active)</span>
            </span>
          ) : null}
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-[90vw] max-w-sm overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Filter mentors</SheetTitle>
          <SheetDescription>Narrow results by field, location, language, price and availability.</SheetDescription>
        </SheetHeader>
        <div className="px-4 pb-6">
          <MentorFilters taxonomy={taxonomy} params={params} idPrefix="mobile" onApplied={() => setOpen(false)} />
        </div>
      </SheetContent>
    </Sheet>
  );
}
