"use client";

import { useState } from "react";
import { Heart } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/data/client";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/common/page-header";
import { Pager } from "@/components/common/pager";
import { QueryView } from "@/components/common/query-view";
import { EmptyState } from "@/components/feedback/empty-state";
import { CardListSkeleton } from "@/components/feedback/loading-state";
import { MentorCard } from "@/components/mentors/mentor-card";
import { SaveMentorButton } from "@/components/mentors/save-mentor-button";
import { useApiQuery } from "@/hooks/use-api-query";

export function SavedMentors() {
  const [page, setPage] = useState(1);
  const query = useApiQuery(`student:saved:${page}`, () => api.student.savedMentors(page));

  return (
    <div className="grid grid-cols-1 gap-6">
      <PageHeader title="Saved mentors" description="Mentors you've saved to compare and book later." />
      <QueryView
        query={query}
        errorTitle="Couldn't load saved mentors"
        loading={<CardListSkeleton count={3} className="md:grid-cols-2 xl:grid-cols-3" />}
      >
        {(page) =>
          page.results.length === 0 ? (
            <EmptyState
              icon={Heart}
              title="No saved mentors yet"
              description="Use the Save button on a mentor's profile to keep track of people you'd like to book."
              action={
                <Button asChild>
                  <Link href="/mentors">Browse mentors</Link>
                </Button>
              }
            />
          ) : (
            <ul className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              {page.results.map((mentor) => (
                <li key={mentor.id}>
                  <MentorCard
                    mentor={mentor}
                    action={
                      <SaveMentorButton
                        mentorId={mentor.slug}
                        initialSaved
                        onChange={(saved) => {
                          if (!saved) {
                            query.mutate((p) => ({
                              ...p,
                              count: p.count - 1,
                              results: p.results.filter((m) => m.id !== mentor.id),
                            }));
                          }
                        }}
                      />
                    }
                  />
                </li>
              ))}
            </ul>
          )
        }
      </QueryView>
      <Pager page={page} count={query.data?.count ?? 0} onPageChange={setPage} />
    </div>
  );
}
