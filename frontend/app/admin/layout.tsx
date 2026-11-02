"use client";

import type { ReactNode } from "react";
import { AppShell, type NavGroup } from "@/components/AppShell";
import { StaffLogin } from "@/components/StaffLogin";
import { SessionProvider } from "@/components/SessionProvider";
import { Icon } from "@/components/icons";
import { LoadingState } from "@/components/ui";
import { hasRole, useSession, type Me } from "@/lib/session";

function buildNav(me: Me): NavGroup[] {
  if (me.is_super_admin) {
    return [
      { items: [{ href: "/admin", label: "Overview", icon: <Icon.Dashboard size={18} /> }] },
      {
        label: "Platform",
        items: [
          { href: "/admin/registrations", label: "Registrations", icon: <Icon.Inbox size={18} /> },
          { href: "/admin/institutions", label: "Institutions", icon: <Icon.Building size={18} /> },
          { href: "/admin/reports", label: "Reports", icon: <Icon.Chart size={18} /> },
        ],
      },
      {
        label: "Global library",
        items: [
          { href: "/admin/global", label: "Review & generate", icon: <Icon.Globe size={18} /> },
        ],
      },
      { label: "Account", items: [{ href: "/admin/settings", label: "Security", icon: <Icon.Settings size={18} /> }] },
    ];
  }

  const groups: NavGroup[] = [
    { items: [{ href: "/admin", label: "Overview", icon: <Icon.Dashboard size={18} /> }] },
  ];

  const isAdmin = hasRole(me, "institution_admin");
  const isStaff = hasRole(me, "institution_admin", "teacher");

  if (isAdmin) {
    groups.push({
      label: "Institution",
      items: [
        { href: "/admin/academic", label: "Academic structure", icon: <Icon.Layers size={18} /> },
        { href: "/admin/people", label: "People", icon: <Icon.Users size={18} /> },
      ],
    });
  }

  if (isStaff) {
    groups.push({
      label: "Assessment",
      items: [
        { href: "/admin/questions", label: "Question bank", icon: <Icon.FileText size={18} /> },
        { href: "/admin/ai", label: "AI generation", icon: <Icon.Sparkles size={18} /> },
        { href: "/admin/exams", label: "Exams", icon: <Icon.ClipboardCheck size={18} /> },
        { href: "/admin/results", label: "Results & reports", icon: <Icon.Chart size={18} /> },
      ],
    });
  }

  if (hasRole(me, "central_academic_reviewer")) {
    groups.push({
      label: "Global library",
      items: [{ href: "/admin/global", label: "Review & generate", icon: <Icon.Globe size={18} /> }],
    });
  }

  groups.push({
    label: "Account",
    items: [{ href: "/admin/settings", label: "Security", icon: <Icon.Settings size={18} /> }],
  });
  return groups;
}

export default function AdminLayout({ children }: { children: ReactNode }) {
  const session = useSession();
  const { me, loading, reload, signOut } = session;

  if (loading) {
    return (
      <div style={{ display: "grid", placeItems: "center", minHeight: "100vh" }}>
        <LoadingState label="Loading your workspace…" />
      </div>
    );
  }

  if (!me) return <StaffLogin onSignedIn={reload} />;

  if (me.roles.includes("student") && !me.is_super_admin && me.roles.length === 1) {
    // A pure student landed on the staff portal — guide them without removing access.
    if (typeof window !== "undefined") window.location.replace("/student");
    return null;
  }

  return (
    <SessionProvider value={session}>
      <AppShell me={me} nav={buildNav(me)} onSignOut={signOut}>
        {children}
      </AppShell>
    </SessionProvider>
  );
}
