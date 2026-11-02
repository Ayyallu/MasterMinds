"use client";

import { createContext, useContext, type ReactNode } from "react";
import type { Me, SessionState } from "@/lib/session";

const Ctx = createContext<SessionState | null>(null);

export function SessionProvider({ value, children }: { value: SessionState; children: ReactNode }) {
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

/** Access the authenticated user inside the staff shell. Guaranteed non-null there. */
export function useMe(): Me {
  const ctx = useContext(Ctx);
  if (!ctx || !ctx.me) throw new Error("useMe must be used inside an authenticated shell");
  return ctx.me;
}

export function useSessionCtx(): SessionState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSessionCtx must be used inside SessionProvider");
  return ctx;
}
