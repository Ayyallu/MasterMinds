"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { Icon } from "./icons";
import { Button, cx } from "./ui";
import { initials, type Me, primaryRoleLabel } from "@/lib/session";

export type NavItem = { href: string; label: string; icon: ReactNode };
export type NavGroup = { label?: string; items: NavItem[] };

export function AppShell({
  me,
  nav,
  accent,
  onSignOut,
  children,
}: {
  me: Me;
  nav: NavGroup[];
  accent?: string;
  onSignOut: () => void;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const isActive = (href: string) =>
    pathname === href || (href !== "/admin" && href !== "/student" && pathname.startsWith(href));
  const activeLabel = nav.flatMap((g) => g.items).find((i) => isActive(i.href))?.label;

  return (
    <div className="shell" style={accent ? ({ ["--accent" as string]: accent } as React.CSSProperties) : undefined}>
      {open && <div className="sidebar-backdrop" onClick={() => setOpen(false)} />}
      <aside className={cx("sidebar", open && "open")}>
        <Link href="/" className="sidebar-brand">
          <span className="sidebar-logo">
            <Icon.GraduationCap size={20} />
          </span>
          MasterMinds
        </Link>
        <nav className="stack gap-1">
          {nav.map((group, gi) => (
            <div key={gi} className="stack gap-1">
              {group.label && <span className="sidebar-group-label">{group.label}</span>}
              {group.items.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cx("nav-link", isActive(item.href) && "active")}
                  onClick={() => setOpen(false)}
                >
                  {item.icon}
                  {item.label}
                </Link>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="sidebar-user">
            <span className="avatar">{initials(me.full_name)}</span>
            <div className="stack" style={{ minWidth: 0 }}>
              <span className="sidebar-user-name">{me.full_name}</span>
              <span className="sidebar-user-role">{primaryRoleLabel(me)}</span>
            </div>
          </div>
        </div>
      </aside>

      <div className="shell-main">
        <header className="topbar">
          <button
            className="btn btn-ghost btn-icon topbar-mobile-btn"
            onClick={() => setOpen((o) => !o)}
            aria-label="Toggle navigation"
          >
            <Icon.Menu size={20} />
          </button>
          <div className="row gap-3 grow" style={{ minWidth: 0 }}>
            <span className="topbar-title">{activeLabel ?? `${primaryRoleLabel(me)} workspace`}</span>
          </div>
          <div className="row gap-3">
            {me.email && <span className="topbar-chip">{me.email}</span>}
            <Button variant="secondary" size="sm" icon={<Icon.Logout size={16} />} onClick={onSignOut}>
              Sign out
            </Button>
          </div>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
