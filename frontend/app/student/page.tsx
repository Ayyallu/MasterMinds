"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, clearTokens, getToken, setRefreshToken, setToken } from "@/lib/api";
import { AuthLayout } from "@/components/AuthLayout";
import { StudentShell } from "@/components/StudentShell";
import { InstitutionProfileCard, useInstitutionProfile } from "@/components/Institution";
import { Icon } from "@/components/icons";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  LoadingState,
  StatusBadge,
  useToast,
} from "@/components/ui";

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
type StudentMe = { id: number; full_name: string; email: string | null; roles: string[]; institution_ids: number[] };

export default function StudentHome() {
  const toast = useToast();
  const [me, setMe] = useState<StudentMe | null>(null);
  const [exams, setExams] = useState<StudentExam[]>([]);
  const [institutionCode, setInstitutionCode] = useState("");
  const [registerNumber, setRegisterNumber] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState<number | null>(null);

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

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

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

  async function startExam(exam: StudentExam) {
    setStarting(exam.id);
    setError(null);
    try {
      const attempt = await api<{ id: number }>(`/exams/${exam.id}/attempts/start`, { method: "POST" });
      window.location.href = `/student/attempts/${attempt.id}`;
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Could not start exam.", "error");
      setStarting(null);
    }
  }

  if (loading) {
    return (
      <div style={{ display: "grid", placeItems: "center", minHeight: "100vh" }}>
        <LoadingState label="Loading your student portal…" />
      </div>
    );
  }

  if (!me) {
    return (
      <AuthLayout
        eyebrow="Student portal"
        title="Welcome back"
        subtitle="Sign in with the institution code and register number supplied by your school or college."
        footer={
          <>
            New here? <Link href="/student/register">Register for admin approval</Link>
          </>
        }
      >
        <form className="stack gap-4" onSubmit={signIn}>
          <Field label="Institution code">
            <Input autoComplete="organization" required value={institutionCode} onChange={(e) => setInstitutionCode(e.target.value)} aria-label="Institution code" />
          </Field>
          <Field label="Register number">
            <Input autoComplete="username" required value={registerNumber} onChange={(e) => setRegisterNumber(e.target.value)} aria-label="Register number" />
          </Field>
          <Field label="Password">
            <Input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} aria-label="Password" />
          </Field>
          {error && <Alert tone="error">{error}</Alert>}
          <Button type="submit" block size="lg" loading={busy}>
            Sign in
          </Button>
        </form>
      </AuthLayout>
    );
  }

  const upcoming = exams.filter((e) => e.can_start || e.attempts.some((a) => a.status === "in_progress"));

  return (
    <StudentShell userName={me.full_name} institutionId={me.institution_ids[0]} onSignOut={signOut}>
      <div className="page-header">
        <div>
          <span className="badge badge-accent">Student dashboard</span>
          <h1 className="page-title" style={{ marginTop: "var(--s-3)" }}>
            Your exams
          </h1>
          <p className="page-subtitle">Resume an active attempt, start an available exam, and review released results.</p>
        </div>
        {upcoming.length > 0 && <Badge tone="success" dot>{upcoming.length} available now</Badge>}
      </div>

      {error && <Alert tone="error">{error}</Alert>}

      <StudentInstitutionCard institutionId={me.institution_ids[0]} />

      {exams.length === 0 ? (
        <Card>
          <EmptyState icon={<Icon.Calendar size={24} />} title="No exams to show yet">
            Your eligible exams will appear here once your institution schedules them.
          </EmptyState>
        </Card>
      ) : (
        <div className="grid grid-cards">
          {exams.map((exam) => {
            const active = exam.attempts.find((a) => a.status === "in_progress");
            const completed = exam.attempts.filter((a) => a.status !== "in_progress");
            return (
              <Card key={exam.id} className="stack gap-3">
                <div className="row between">
                  <StatusBadge status={exam.status} />
                  {exam.results_published && <Badge tone="accent">Results out</Badge>}
                </div>
                <div>
                  <h3 style={{ marginBottom: 2 }}>{exam.title}</h3>
                  <p className="muted text-sm">{exam.institution_name}</p>
                </div>
                <div className="row gap-4 text-sm muted wrap">
                  <span className="row gap-1">
                    <Icon.Clock size={14} /> {exam.duration_minutes} min
                  </span>
                  <span className="row gap-1">
                    <Icon.ClipboardCheck size={14} /> {exam.attempt_limit} attempt{exam.attempt_limit === 1 ? "" : "s"}
                  </span>
                </div>
                {exam.start_at && (
                  <p className="text-sm">
                    <span className="muted">Opens</span> {new Date(exam.start_at).toLocaleString()}
                  </p>
                )}

                <div style={{ marginTop: "auto" }}>
                  {active ? (
                    <Link href={`/student/attempts/${active.id}`} className="btn btn-primary btn-block">
                      Resume exam <Icon.ArrowRight size={16} />
                    </Link>
                  ) : exam.can_start ? (
                    <Button block loading={starting === exam.id} onClick={() => startExam(exam)}>
                      Start exam
                    </Button>
                  ) : (
                    <p className="muted text-sm">Not currently available to start.</p>
                  )}
                </div>

                {completed.length > 0 && (
                  <div className="stack gap-2" style={{ borderTop: "1px solid var(--border)", paddingTop: "var(--s-3)" }}>
                    <span className="text-xs muted" style={{ fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                      Previous attempts
                    </span>
                    {completed.map((attempt) => (
                      <div key={attempt.id} className="row between text-sm">
                        <span>
                          Attempt {attempt.attempt_no} · {attempt.status.replaceAll("_", " ")}
                        </span>
                        {exam.results_published ? (
                          <Link href={`/student/results/${attempt.id}`}>View result</Link>
                        ) : (
                          <span className="faint">Not released</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </StudentShell>
  );
}

function StudentInstitutionCard({ institutionId }: { institutionId: number | undefined }) {
  const { data } = useInstitutionProfile(institutionId);
  if (!data) return null;
  return (
    <div style={{ marginBottom: "var(--s-6)" }}>
      <InstitutionProfileCard profile={data} />
    </div>
  );
}
