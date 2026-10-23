"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, clearTokens, getToken, setRefreshToken, setToken } from "@/lib/api";
import "./student.css";

type Attempt = {
  id: number;
  attempt_no: number;
  status: string;
  started_at: string;
  submitted_at: string | null;
};
type StudentExam = {
  id: number;
  institution_id: number;
  institution_name: string;
  title: string;
  status: string;
  start_at: string | null;
  end_at: string | null;
  duration_minutes: number;
  attempt_limit: number;
  results_published: boolean;
  can_start: boolean;
  attempts: Attempt[];
};
type StudentMe = {
  id: number;
  full_name: string;
  email: string | null;
  roles: string[];
};

export default function StudentHome() {
  const [me, setMe] = useState<StudentMe | null>(null);
  const [exams, setExams] = useState<StudentExam[]>([]);
  const [institutionCode, setInstitutionCode] = useState("");
  const [registerNumber, setRegisterNumber] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    if (!getToken()) {
      setMe(null);
      setExams([]);
      setLoading(false);
      return;
    }
    try {
      const [user, data] = await Promise.all([
        api<StudentMe>("/auth/me"),
        api<StudentExam[]>("/student/exams"),
      ]);
      if (!user.roles.includes("student")) {
        throw new Error("This account does not have student access.");
      }
      setMe(user);
      setExams(data);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not load your dashboard.";
      if (message.includes("student access") || message.includes("Insufficient role")) {
        setError(message);
      } else {
        clearTokens();
        setMe(null);
        setExams([]);
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadDashboard(); }, [loadDashboard]);

  async function signIn(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await api<{ access_token: string; refresh_token: string }>("/auth/login", {
        method: "POST",
        auth: false,
        body: {
          institution_code: institutionCode.trim(),
          register_number: registerNumber.trim(),
          password,
        },
      });
      setToken(result.access_token);
      setRefreshToken(result.refresh_token);
      setPassword("");
      setLoading(true);
      await loadDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed.");
    } finally {
      setBusy(false);
    }
  }

  function signOut() {
    clearTokens();
    setMe(null);
    setExams([]);
    setError(null);
  }

  if (loading) {
    return <main className="student-shell"><p className="student-muted">Loading your student portal…</p></main>;
  }

  if (!me) {
    return (
      <main className="student-shell">
        <div className="student-topbar">
          <Link className="student-brand" href="/">MasterMinds</Link>
          <Link className="student-button secondary" href="/student/register">Create student account</Link>
        </div>
        <section className="student-card" style={{ maxWidth: 560, margin: "4vh auto" }}>
          <p className="student-pill">STUDENT PORTAL</p>
          <h1>Welcome back</h1>
          <p className="student-muted">Sign in with the institution code and register number supplied by your school or college.</p>
          <form className="student-form" onSubmit={signIn}>
            <label className="student-label">Institution code
              <input className="student-input" autoComplete="organization" required value={institutionCode} onChange={e => setInstitutionCode(e.target.value)} />
            </label>
            <label className="student-label">Register number
              <input className="student-input" autoComplete="username" required value={registerNumber} onChange={e => setRegisterNumber(e.target.value)} />
            </label>
            <label className="student-label">Password
              <input className="student-input" type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} />
            </label>
            {error && <p className="student-error" role="alert">{error}</p>}
            <button className="student-button" type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
          </form>
          <p className="student-muted" style={{ marginTop: "1.25rem" }}>New here? <Link href="/student/register">Register for admin approval</Link>.</p>
        </section>
      </main>
    );
  }

  return (
    <main className="student-shell">
      <div className="student-topbar">
        <Link className="student-brand" href="/">MasterMinds</Link>
        <div style={{ display: "flex", alignItems: "center", gap: ".8rem" }}>
          <span className="student-muted">Signed in as <strong>{me.full_name}</strong></span>
          <button className="student-button secondary" onClick={signOut}>Sign out</button>
        </div>
      </div>
      <section style={{ marginBottom: "1.5rem" }}>
        <p className="student-pill">STUDENT DASHBOARD</p>
        <h1 style={{ marginBottom: ".35rem" }}>Your exams</h1>
        <p className="student-muted">See scheduled exams, resume an active attempt, and review results when your institution releases them.</p>
      </section>
      {error && <p className="student-error" role="alert">{error}</p>}
      {exams.length === 0 ? (
        <section className="student-card">
          <h2>No exams to show yet</h2>
          <p className="student-muted">Your eligible exams will appear here when your institution schedules them.</p>
        </section>
      ) : (
        <div className="student-grid">
          {exams.map(exam => {
            const active = exam.attempts.find(a => a.status === "in_progress");
            const completed = exam.attempts.filter(a => a.status !== "in_progress");
            return (
              <article className="student-card" key={exam.id}>
                <span className="student-pill">{exam.status.replaceAll("_", " ")}</span>
                <h2>{exam.title}</h2>
                <p className="student-muted">{exam.institution_name}</p>
                <p className="student-muted">{exam.duration_minutes} minutes · {exam.attempt_limit} allowed attempt{exam.attempt_limit === 1 ? "" : "s"}</p>
                {exam.start_at && <p><strong>Starts:</strong> {new Date(exam.start_at).toLocaleString()}</p>}
                {exam.end_at && <p><strong>Ends:</strong> {new Date(exam.end_at).toLocaleString()}</p>}
                {active ? (
                  <Link className="student-button" href={`/student/attempts/${active.id}`}>Resume exam</Link>
                ) : exam.can_start ? (
                  <button className="student-button" onClick={async () => {
                    setError(null);
                    try {
                      const attempt = await api<{ id: number }>(`/exams/${exam.id}/attempts/start`, { method: "POST" });
                      window.location.href = `/student/attempts/${attempt.id}`;
                    } catch (err) { setError(err instanceof Error ? err.message : "Could not start exam."); }
                  }}>Start exam</button>
                ) : <p className="student-muted">Not currently available to start.</p>}
                {completed.length > 0 && <div style={{ marginTop: "1rem" }}>
                  <strong>Previous attempts</strong>
                  <ul>{completed.map(attempt => (
                    <li key={attempt.id}>
                      Attempt {attempt.attempt_no}: {attempt.status.replaceAll("_", " ")}
                      {" · "}
                      {exam.results_published
                        ? <Link href={`/student/results/${attempt.id}`}>View result</Link>
                        : <span className="student-muted">Result not released</span>}
                    </li>
                  ))}</ul>
                </div>}
              </article>
            );
          })}
        </div>
      )}
    </main>
  );
}
