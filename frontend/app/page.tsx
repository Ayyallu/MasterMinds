import Link from "next/link";
import HealthStatus from "@/components/HealthStatus";

export default function Home() {
  return (
    <main style={{ maxWidth: 900, margin: "0 auto" }}>
      <p style={{ fontWeight: 800, letterSpacing: "-.03em" }}>MasterMinds</p>
      <h1>Online examinations, made simpler.</h1>
      <p style={{ maxWidth: 620, lineHeight: 1.6 }}>
        A secure online examination platform for schools and colleges. Sign in to take an exam, or manage your institution.
      </p>
      <div style={{ display: "flex", gap: ".75rem", flexWrap: "wrap", margin: "1.5rem 0 2.5rem" }}>
        <Link href="/student" style={{ display: "inline-block", padding: ".8rem 1rem", borderRadius: 9, background: "#233b72", color: "white", fontWeight: 700, textDecoration: "none" }}>
          Student portal
        </Link>
        <Link href="/student/register" style={{ display: "inline-block", padding: ".8rem 1rem", borderRadius: 9, background: "#eef2f8", color: "#233b72", fontWeight: 700, textDecoration: "none" }}>
          Student registration
        </Link>
        <Link href="/admin" style={{ display: "inline-block", padding: ".8rem 1rem", borderRadius: 9, border: "1px solid #cbd5e1", color: "#172033", fontWeight: 700, textDecoration: "none" }}>
          Admin portal
        </Link>
      </div>
      <HealthStatus />
    </main>
  );
}
