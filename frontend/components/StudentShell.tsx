"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Icon } from "./icons";
import { Button } from "./ui";
import { initials } from "@/lib/session";

/** Top-bar shell for the student portal (no sidebar — fewer, focused screens). */
export function StudentShell({
  userName,
  right,
  onSignOut,
  children,
  maxWidth = 1080,
}: {
  userName?: string;
  right?: ReactNode;
  onSignOut?: () => void;
  children: ReactNode;
  maxWidth?: number;
}) {
  return (
    <div style={{ minHeight: "100vh" }}>
      <header className="topbar" style={{ position: "sticky", top: 0 }}>
        <Link href="/student" className="brand" style={{ fontSize: "var(--text-md)" }}>
          <span className="sidebar-logo">
            <Icon.GraduationCap size={18} />
          </span>
          MasterMinds
        </Link>
        <div className="row gap-3">
          {right}
          {userName && (
            <span className="row gap-2">
              <span className="avatar" style={{ width: 32, height: 32, fontSize: "var(--text-xs)", background: "var(--grad-brand)", color: "#fff" }}>
                {initials(userName)}
              </span>
              <span className="text-sm strong" style={{ whiteSpace: "nowrap" }}>
                {userName}
              </span>
            </span>
          )}
          {onSignOut && (
            <Button variant="secondary" size="sm" icon={<Icon.Logout size={16} />} onClick={onSignOut}>
              Sign out
            </Button>
          )}
        </div>
      </header>
      <main className="content" style={{ maxWidth }}>{children}</main>
    </div>
  );
}
