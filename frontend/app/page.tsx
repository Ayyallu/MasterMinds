import Link from "next/link";
import HealthStatus from "@/components/HealthStatus";
import { Icon } from "@/components/icons";

const features = [
  {
    icon: <Icon.Shield size={20} />,
    title: "Secure, tenant-isolated",
    body: "Server-enforced role-based access and institution isolation keep every school's data separate and private.",
  },
  {
    icon: <Icon.ClipboardCheck size={20} />,
    title: "Reliable exam delivery",
    body: "Server-authoritative timing, idempotent autosave and disconnect-resume keep attempts safe to the last second.",
  },
  {
    icon: <Icon.Sparkles size={20} />,
    title: "AI-assisted authoring",
    body: "Generate reviewed question candidates pre-exam, with human approval gates before anything reaches students.",
  },
  {
    icon: <Icon.Chart size={20} />,
    title: "Scoring & reporting",
    body: "Deterministic, reproducible scoring with controlled result release and role-scoped reports.",
  },
];

export default function Home() {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header className="public-nav">
        <span className="brand">
          <span className="sidebar-logo">
            <Icon.GraduationCap size={20} />
          </span>
          MasterMinds
        </span>
        <div className="row gap-3">
          <Link href="/student" className="btn btn-ghost btn-sm">
            Student sign in
          </Link>
          <Link href="/admin" className="btn btn-primary btn-sm">
            Admin sign in
          </Link>
        </div>
      </header>

      <main className="grow">
        {/* Hero */}
        <section style={{ maxWidth: "var(--maxw)", margin: "0 auto", padding: "var(--s-16) var(--s-6) var(--s-12)" }}>
          <div style={{ maxWidth: 680 }}>
            <span className="badge badge-accent" style={{ marginBottom: "var(--s-5)" }}>
              Online examination platform
            </span>
            <h1 style={{ fontSize: "var(--text-3xl)", lineHeight: 1.1, marginBottom: "var(--s-4)" }}>
              Online examinations, made simpler and secure.
            </h1>
            <p className="muted" style={{ fontSize: "var(--text-lg)", maxWidth: 560, marginBottom: "var(--s-8)" }}>
              A secure examination platform for schools and colleges — from question banks and
              AI-assisted authoring to reliable delivery, scoring and reporting.
            </p>
            <div className="row gap-3 wrap">
              <Link href="/student" className="btn btn-primary btn-lg" style={{ gap: "var(--s-2)" }}>
                Take an exam <Icon.ArrowRight size={18} />
              </Link>
              <Link href="/student/register" className="btn btn-secondary btn-lg">
                Register as a student
              </Link>
              <Link href="/admin" className="btn btn-ghost btn-lg">
                Manage an institution
              </Link>
            </div>
          </div>
        </section>

        {/* Features */}
        <section style={{ maxWidth: "var(--maxw)", margin: "0 auto", padding: "0 var(--s-6) var(--s-16)" }}>
          <div className="grid grid-cards">
            {features.map((f) => (
              <div className="card card-pad" key={f.title}>
                <span className="stat-icon" style={{ width: 40, height: 40, marginBottom: "var(--s-4)" }}>
                  {f.icon}
                </span>
                <h3 style={{ marginBottom: "var(--s-2)" }}>{f.title}</h3>
                <p className="muted text-sm">{f.body}</p>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer style={{ borderTop: "1px solid var(--border)", background: "var(--bg-surface)" }}>
        <div
          className="row between wrap gap-3"
          style={{ maxWidth: "var(--maxw)", margin: "0 auto", padding: "var(--s-5) var(--s-6)" }}
        >
          <span className="muted text-sm">© {new Date().getFullYear()} MasterMinds</span>
          <HealthStatus />
        </div>
      </footer>
    </div>
  );
}
