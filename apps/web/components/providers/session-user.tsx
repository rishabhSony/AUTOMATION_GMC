"use client";

import { createContext, useContext } from "react";

import type { UserRole } from "@/lib/api/types";

export type SessionUser = {
  id: string;
  email: string;
  fullName: string;
  role: UserRole;
};

const SessionUserContext = createContext<SessionUser | null>(null);

/** The signed-in QuotePulse user, resolved on the server in app/(app)/layout.tsx. */
export function SessionUserProvider({
  user,
  children,
}: {
  user: SessionUser;
  children: React.ReactNode;
}) {
  return (
    <SessionUserContext.Provider value={user}>
      {children}
    </SessionUserContext.Provider>
  );
}

export function useSessionUser(): SessionUser {
  const user = useContext(SessionUserContext);
  if (!user) throw new Error("useSessionUser outside SessionUserProvider");
  return user;
}

// Role sets from Backend Schema v4.0 §8; the API enforces them, the UI only hides controls.
export const CAN = {
  editQuote: ["sales_rm", "underwriter", "admin"],
  approveSublimit: ["underwriter", "admin"],
  recalculateAge: ["ops_analyst", "underwriter", "admin"],
  resolveException: ["ops_analyst", "underwriter", "admin"],
} satisfies Record<string, UserRole[]>;

export function useCan(action: keyof typeof CAN): boolean {
  return (CAN[action] as UserRole[]).includes(useSessionUser().role);
}
