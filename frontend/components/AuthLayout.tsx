import Link from "next/link";
import type { ReactNode } from "react";
import { Icon } from "./icons";

const points = [
  { icon: <Icon.Shield size={16} />, text: "Tenant-isolated, role-based access for every institution." },
  { icon: <Icon.Clock size={16} />, text: "Server-timed exams with autosave and disconnect-resume." },
  { icon: <Icon.Sparkles size={16} />, text: "AI-assisted authoring behind human review gates." },
];

/** Split layout for public auth screens (login / register): brand panel + form. */
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
    <div className="auth-split">
      <aside className="auth-aside" aria-hidden="true">
        <span className="blob" style={{ width: 360, height: 360, background: "#6366f1", top: -120, right: -100 }} />
        <span className="blob" style={{ width: 300, height: 300, background: "#c026d3", bottom: -100, left: -80, animationDelay: "-6s" }} />
        <Link href="/" className="brand" tabIndex={-1}>
          <span className="sidebar-logo">
            <Icon.GraduationCap size={20} />
          </span>
          MasterMinds
        </Link>
        <div className="stack gap-6">
          <h2>Exams your institution can trust.</h2>
          <div className="stack gap-4">
            {points.map((p) => (
              <div className="auth-point" key={p.text}>
                <span className="auth-point-icon">{p.icon}</span>
                <span style={{ paddingTop: 5 }}>{p.text}</span>
              </div>
            ))}
          </div>
        </div>
        <span className="text-xs" style={{ color: "#8d93c4" }}>
          © {new Date().getFullYear()} MasterMinds
        </span>
      </aside>

      <div className="auth-main">
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
          <div className="auth-panel">
            <div style={{ marginBottom: "var(--s-6)" }}>
              <span className="badge badge-accent">{eyebrow}</span>
              <h1 style={{ marginTop: "var(--s-4)", fontSize: "var(--text-2xl)" }}>{title}</h1>
              {subtitle && (
                <p className="muted" style={{ marginTop: "var(--s-2)" }}>
                  {subtitle}
                </p>
              )}
            </div>
            <div className="card card-pad" style={{ boxShadow: "var(--shadow-lg)", padding: "var(--s-8)" }}>
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
    </div>
  );
}
