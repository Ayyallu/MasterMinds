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

const highlights = [
  { value: "4", label: "Question types" },
  { value: "100%", label: "Server-timed attempts" },
  { value: "2-step", label: "Human review gates" },
  { value: "0", label: "Answer keys sent to students" },
];

export default function Home() {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", position: "relative", overflow: "hidden", isolation: "isolate" }}>
      <span className="blob" style={{ width: 520, height: 520, background: "#818cf8", top: -200, left: "50%", marginLeft: -520 }} />
      <span className="blob" style={{ width: 460, height: 460, background: "#e879f9", top: -120, left: "50%", marginLeft: 40, animationDelay: "-7s" }} />

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
        <section className="hero">
          <span className="badge badge-accent">
            <Icon.Sparkles size={14} /> Online examination platform
          </span>
          <h1 className="hero-title">
            Online examinations, made <span className="gradient-text">simpler and secure.</span>
          </h1>
          <p className="hero-sub">
            A secure examination platform for schools and colleges — from question banks and
            AI-assisted authoring to reliable delivery, scoring and reporting.
          </p>
          <div className="hero-actions">
            <Link href="/student" className="btn btn-primary btn-lg">
              Take an exam <Icon.ArrowRight size={18} />
            </Link>
            <Link href="/student/register" className="btn btn-secondary btn-lg">
              Register as a student
            </Link>
            <Link href="/admin" className="btn btn-ghost btn-lg">
              Manage an institution
            </Link>
          </div>
        </section>

        {/* Highlights strip */}
        <section style={{ maxWidth: "var(--maxw)", margin: "0 auto", padding: "0 var(--s-6) var(--s-10)" }}>
          <div className="card" style={{ background: "var(--bg-glass)", backdropFilter: "blur(14px)" }}>
            <div className="grid grid-stats card-pad" style={{ textAlign: "center" }}>
              {highlights.map((h) => (
                <div key={h.label} className="stack gap-1">
                  <span className="stat-value gradient-text" style={{ fontSize: "var(--text-2xl)" }}>
                    {h.value}
                  </span>
                  <span className="muted text-sm">{h.label}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Features */}
        <section style={{ maxWidth: "var(--maxw)", margin: "0 auto", padding: "0 var(--s-6) var(--s-16)" }}>
          <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))" }}>
            {features.map((f) => (
              <div className="card card-interactive feature-card" key={f.title}>
                <span className="stat-icon">{f.icon}</span>
                <h3>{f.title}</h3>
                <p className="muted text-sm">{f.body}</p>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer style={{ borderTop: "1px solid var(--border)", background: "var(--bg-glass)", backdropFilter: "blur(12px)" }}>
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
