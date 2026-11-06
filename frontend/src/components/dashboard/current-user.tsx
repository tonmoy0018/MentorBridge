"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import type { CurrentUser } from "@/lib/api/types";

interface CurrentUserContextValue {
  user: CurrentUser;
  setUser: (user: CurrentUser) => void;
}

const CurrentUserContext = createContext<CurrentUserContextValue | null>(null);

export function CurrentUserProvider({ user: initialUser, children }: { user: CurrentUser; children: ReactNode }) {
  const [user, setUser] = useState(initialUser);
  return <CurrentUserContext value={{ user, setUser }}>{children}</CurrentUserContext>;
}

export function useCurrentUser(): CurrentUserContextValue {
  const value = useContext(CurrentUserContext);
  if (!value) throw new Error("useCurrentUser must be used inside a dashboard layout");
  return value;
}
