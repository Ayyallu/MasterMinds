"use client";

import { useState } from "react";
import { api, getToken } from "@/lib/api";
import { useMe } from "@/components/SessionProvider";
import { Icon } from "@/components/icons";
import { ReportView, type ExamReport } from "@/components/ReportView";
import {
  Alert,
  Button,
  Card,
  CardHeader,
  Field,
  Input,
  PageHeader,
  Spinner,
  Stat,
  useToast,
} from "@/components/ui";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function ResultsPage() {
  const me = useMe();
  const toast = useToast();
  const institutionId = me.institution_ids[0];
  const isAdmin = me.roles.includes("institution_admin") || me.is_super_admin;

  const [examId, setExamId] = useState("");
  const [report, setReport] = useState<ExamReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);

  const base = `/institutions/${institutionId}/exams/${Number(examId)}`;

  async function loadReport(e?: React.FormEvent) {
    e?.preventDefault();
    setLoading(true);
    setError(null);
    try {
      setReport(await api<ExamReport>(`${base}/report`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load report.");
      setReport(null);
    } finally {
      setLoading(false);
    }
  }

  async function act(path: string, label: string) {
    setActing(true);
    try {
      await api(`${base}${path}`, { method: "POST" });
      toast.push(label, "success");
      await loadReport();
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Action failed.", "error");
    } finally {
      setActing(false);
    }
  }

  async function downloadCsv() {
    try {
      const resp = await fetch(`${API_BASE}${base}/report.csv`, {
        headers: { Authorization: `Bearer ${getToken() ?? ""}` },
      });
      if (!resp.ok) throw new Error(`Export failed (${resp.status})`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `exam-${examId}-report.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Export failed.", "error");
    }
  }

  if (!institutionId) {
    return (
      <>
        <PageHeader title="Results & reports" />
        <Card>
          <p className="muted">No institution is linked to your account.</p>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader title="Results & reports" subtitle="Score attempts, release results, export reports and apply audited corrections." />

      <Card style={{ maxWidth: 560, marginBottom: "var(--s-6)" }}>
        <form className="card-pad row gap-3 items-start wrap" onSubmit={loadReport}>
          <Field label="Exam ID">
            <Input inputMode="numeric" value={examId} onChange={(e) => setExamId(e.target.value.replace(/[^0-9]/g, ""))} placeholder="e.g. 340" aria-label="Exam ID" required />
          </Field>
          <div style={{ alignSelf: "flex-end" }} className="row gap-2">
            <Button type="submit" icon={<Icon.Search size={16} />} loading={loading} disabled={!examId}>
              Load report
            </Button>
            {report && (
              <Button type="button" variant="secondary" icon={<Icon.Upload size={16} />} onClick={downloadCsv}>
                Export CSV
              </Button>
            )}
          </div>
          {error && (
            <div style={{ flexBasis: "100%" }}>
              <Alert tone="error">{error}</Alert>
            </div>
          )}
        </form>
      </Card>

      {isAdmin && examId && (
        <Card pad={false} style={{ marginBottom: "var(--s-6)" }}>
          <CardHeader title="Admin actions" action={acting ? <Spinner /> : undefined} />
          <div className="card-pad row gap-3 wrap">
            <Button variant="secondary" disabled={acting} onClick={() => act("/score", "Attempts scored.")}>
              Score attempts
            </Button>
            <Button disabled={acting} icon={<Icon.CheckCircle size={16} />} onClick={() => act("/publish-results", "Results published.")}>
              Publish results
            </Button>
          </div>
        </Card>
      )}

      {loading && report === null ? (
        <div className="row gap-3 muted">
          <Spinner /> Loading report…
        </div>
      ) : report ? (
        <ReportView report={report} />
      ) : null}

      {isAdmin && <CensusCard institutionId={institutionId} />}
    </>
  );
}

function CensusCard({ institutionId }: { institutionId: number }) {
  const [date, setDate] = useState("");
  const [result, setResult] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ active_enrollments: number }>(
        `/institutions/${institutionId}/reports/enrollment?census_date=${date}`,
      );
      setResult(res.active_enrollments);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load enrollment report.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card style={{ maxWidth: 560, marginTop: "var(--s-6)" }}>
      <CardHeader title="Enrollment census" />
      <form className="card-pad stack gap-4" onSubmit={run}>
        <p className="muted text-sm">
          Active enrollments as of a census date (counts enrollments that began on/before the date
          and had not ended before it).
        </p>
        <div className="row gap-3 items-start wrap">
          <Field label="Census date">
            <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} aria-label="Census date" required />
          </Field>
          <div style={{ alignSelf: "flex-end" }}>
            <Button type="submit" variant="secondary" loading={busy} disabled={!date}>
              Run
            </Button>
          </div>
        </div>
        {error && <Alert tone="error">{error}</Alert>}
        {result != null && (
          <Stat label={`Active enrollments on ${date}`} value={result} icon={<Icon.Users size={18} />} />
        )}
      </form>
    </Card>
  );
}
