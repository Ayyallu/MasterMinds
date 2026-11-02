import Link from "next/link";
import type { ReactNode } from "react";
import { Icon } from "./icons";

/** Centered split layout for public auth screens (login / register). */
export function AuthLayout({
  eyebrow,
  title,
  subtitle,
  children,
  footer,
}: {
  eyebrow: string;
  title: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: "var(--bg-app)" }}>
      <header className="public-nav">
        <Link href="/" className="brand">
          <span className="sidebar-logo">
            <Icon.GraduationCap size={20} />
          </span>
          MasterMinds
        </Link>
      </header>
      <main
        className="grow"
        style={{ display: "grid", placeItems: "center", padding: "var(--s-6) var(--s-4) var(--s-12)" }}
      >
        <div style={{ width: "100%", maxWidth: 440 }}>
          <div style={{ marginBottom: "var(--s-6)" }}>
            <span className="badge badge-accent">{eyebrow}</span>
            <h1 style={{ marginTop: "var(--s-4)", fontSize: "var(--text-2xl)" }}>{title}</h1>
            {subtitle && (
              <p className="muted" style={{ marginTop: "var(--s-2)" }}>
                {subtitle}
              </p>
            )}
          </div>
          <div className="card card-pad" style={{ boxShadow: "var(--shadow-md)" }}>
            {children}
          </div>
          {footer && (
            <p className="muted text-sm" style={{ textAlign: "center", marginTop: "var(--s-5)" }}>
              {footer}
            </p>
          )}
        </div>
      </main>
    </div>
  );
}
