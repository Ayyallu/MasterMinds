"use client";

import { useCallback, useEffect, useState } from "react";
import { api, clearTokens, getToken } from "@/lib/api";

export type Me = {
  id: number;
  email: string | null;
  full_name: string;
  is_super_admin: boolean;
  roles: string[];
  institution_ids: number[];
};

export type SessionState = {
  me: Me | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  signOut: () => void;
};

/** Loads the current user from /auth/me, exposing role/tenant info. */
export function useSession(): SessionState {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!getToken()) {
      setMe(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      setMe(await api<Me>("/auth/me"));
      setError(null);
    } catch (err) {
      clearTokens();
      setMe(null);
      setError(err instanceof Error ? err.message : "Session expired.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const signOut = useCallback(() => {
    clearTokens();
    setMe(null);
  }, []);

  return { me, loading, error, reload, signOut };
}

export function hasRole(me: Me | null, ...roles: string[]): boolean {
  if (!me) return false;
  if (me.is_super_admin) return true;
  return roles.some((r) => me.roles.includes(r));
}

export function primaryRoleLabel(me: Me | null): string {
  if (!me) return "";
  if (me.is_super_admin) return "Super Admin";
  if (me.roles.includes("institution_admin")) return "Institution Admin";
  if (me.roles.includes("central_academic_reviewer")) return "Central Reviewer";
  if (me.roles.includes("teacher")) return "Faculty";
  if (me.roles.includes("student")) return "Student";
  return "Member";
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p[0]?.toUpperCase() ?? "").join("") || "U";
}
