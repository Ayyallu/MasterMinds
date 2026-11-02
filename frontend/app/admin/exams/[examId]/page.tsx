"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useMe } from "@/components/SessionProvider";
import { Icon } from "@/components/icons";
import { QuestionCard, type QuestionVersion } from "@/components/QuestionView";
import {
  Alert,
  Button,
  Card,
  CardHeader,
  Dialog,
  Field,
  Input,
  LoadingState,
  PageHeader,
  Spinner,
  Stat,
  StatusBadge,
  useToast,
} from "@/components/ui";
import { rememberExam } from "@/lib/recentExams";

type Exam = {
  id: number;
  title: string;
  status: string;
  num_questions: number;
  duration_minutes: number;
  attempt_limit: number;
  randomize: boolean;
  result_release_rule: string;
  frozen: boolean;
  start_at: string | null;
  end_at: string | null;
  timezone: string;
};

export default function ExamDetailPage() {
  const params = useParams<{ examId: string }>();
  const examId = params.examId;
  const me = useMe();
  const toast = useToast();
  const institutionId = me.institution_ids[0];
  const isAdmin = me.roles.includes("institution_admin") || me.is_super_admin;

  const [exam, setExam] = useState<Exam | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);
  const [preview, setPreview] = useState<QuestionVersion[] | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [scheduling, setScheduling] = useState(false);

  const base = `/institutions/${institutionId}/exams/${examId}`;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api<Exam>(base);
      setExam(data);
      if (institutionId) rememberExam(institutionId, data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load exam.");
    } finally {
      setLoading(false);
    }
  }, [base, institutionId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function act(path: string, label: string) {
    setActing(true);
    try {
      const data = await api<Exam>(`${base}${path}`, { method: "POST" });
      setExam(data);
      if (institutionId) rememberExam(institutionId, data);
      toast.push(label, "success");
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Action failed.", "error");
    } finally {
      setActing(false);
    }
  }

  async function loadPreview() {
    setPreviewLoading(true);
    try {
      setPreview(await api<QuestionVersion[]>(`${base}/preview`));
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Could not load preview.", "error");
    } finally {
      setPreviewLoading(false);
    }
  }

  if (loading) return <LoadingState label="Loading exam…" />;
  if (!exam) {
    return (
      <>
        <PageHeader title="Exam" />
        <Alert tone="error">{error ?? "Exam not found."}</Alert>
        <div style={{ marginTop: "var(--s-4)" }}>
          <Link href="/admin/exams" className="btn btn-secondary">
            <Icon.ChevronLeft size={16} /> Back to exams
          </Link>
        </div>
      </>
    );
  }

  const s = exam.status;
  return (
    <>
      <div style={{ marginBottom: "var(--s-4)" }}>
        <Link href="/admin/exams" className="row gap-1 text-sm muted" style={{ width: "fit-content" }}>
          <Icon.ChevronLeft size={16} /> Exams
        </Link>
      </div>
      <PageHeader
        title={exam.title}
        subtitle={
          <span className="row gap-2">
            <span className="mono">#{exam.id}</span> · <StatusBadge status={exam.status} />
            {exam.frozen && <span className="badge badge-neutral">Frozen</span>}
          </span>
        }
        actions={
          <div className="row gap-2 wrap">
            {acting && <Spinner />}
            {s === "draft" && <Button variant="secondary" disabled={acting} onClick={() => act("/submit", "Submitted for approval.")}>Submit for approval</Button>}
            {s === "awaiting_approval" && isAdmin && (
              <>
                <Button variant="success" icon={<Icon.Check size={16} />} disabled={acting} onClick={() => act("/approve", "Exam approved.")}>Approve</Button>
                <Button variant="secondary" disabled={acting} onClick={() => act("/reject", "Exam rejected.")}>Reject</Button>
              </>
            )}
            {s === "approved" && isAdmin && <Button disabled={acting} icon={<Icon.Calendar size={16} />} onClick={() => setScheduling(true)}>Schedule</Button>}
            {isAdmin && ["approved", "scheduled"].includes(s) && (
              <Button variant="ghost" disabled={acting} onClick={() => act("/reopen", "Exam reopened.")}>Reopen</Button>
            )}
          </div>
        }
      />

      <div className="grid grid-stats" style={{ marginBottom: "var(--s-6)" }}>
        <Stat label="Questions" value={exam.num_questions} icon={<Icon.FileText size={18} />} />
        <Stat label="Duration" value={`${exam.duration_minutes}m`} icon={<Icon.Clock size={18} />} />
        <Stat label="Attempts" value={exam.attempt_limit} icon={<Icon.ClipboardCheck size={18} />} />
        <Stat label="Release" value={exam.result_release_rule === "manual" ? "Manual" : "After close"} icon={<Icon.Chart size={18} />} />
      </div>

      <div className="grid grid-cards" style={{ alignItems: "start", marginBottom: "var(--s-6)" }}>
        <Card pad={false}>
          <CardHeader title="Configuration" />
          <div className="card-pad stack gap-3 text-sm">
            <Row label="Randomize per student" value={exam.randomize ? "Yes" : "No"} />
            <Row label="Timezone" value={exam.timezone} />
            <Row label="Starts" value={exam.start_at ? new Date(exam.start_at).toLocaleString() : "Not scheduled"} />
            <Row label="Ends" value={exam.end_at ? new Date(exam.end_at).toLocaleString() : "Not scheduled"} />
          </div>
        </Card>
        <Card pad={false}>
          <CardHeader title="Next steps" />
          <div className="card-pad stack gap-3">
            <p className="muted text-sm" style={{ margin: 0 }}>
              {s === "draft" && "Submit the exam for Institution Admin approval."}
              {s === "awaiting_approval" && "Awaiting Institution Admin approval. Approval selects and freezes the question pool."}
              {s === "approved" && "Approved and frozen. Schedule a window to make it available to students."}
              {s === "scheduled" && "Scheduled. Students can attempt it within the window."}
              {["live", "closed", "results_pending", "published", "archived", "cancelled"].includes(s) &&
                "Manage scoring and result release from Results & reports."}
            </p>
            <div>
              <Link href="/admin/results" className="btn btn-secondary btn-sm">
                Results & reports <Icon.ArrowRight size={14} />
              </Link>
            </div>
          </div>
        </Card>
      </div>

      <Card pad={false}>
        <CardHeader
          title="Question preview"
          action={
            <Button size="sm" variant="secondary" onClick={loadPreview} loading={previewLoading} icon={<Icon.Search size={16} />}>
              {preview ? "Refresh" : "Load preview"}
            </Button>
          }
        />
        <div className="card-pad">
          <Alert tone="info">Preview never shows answer keys — exactly as students will see the questions.</Alert>
          {preview && (
            <div className="stack gap-4" style={{ marginTop: "var(--s-4)" }}>
              {preview.length === 0 ? (
                <p className="muted text-sm">No questions pinned yet. Questions are selected on approval.</p>
              ) : (
                preview.map((q, i) => <QuestionCard key={q.version_id} q={q} index={i} />)
              )}
            </div>
          )}
        </div>
      </Card>

      {scheduling && (
        <ScheduleDialog
          base={base}
          timezone={exam.timezone}
          onClose={() => setScheduling(false)}
          onScheduled={(data) => {
            setExam(data);
            if (institutionId) rememberExam(institutionId, data);
            setScheduling(false);
            toast.push("Exam scheduled.", "success");
          }}
        />
      )}
    </>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="row between">
      <span className="muted">{label}</span>
      <span className="strong">{value}</span>
    </div>
  );
}

function ScheduleDialog({
  base,
  timezone,
  onClose,
  onScheduled,
}: {
  base: string;
  timezone: string;
  onClose: () => void;
  onScheduled: (exam: Exam) => void;
}) {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const data = await api<Exam>(`${base}/schedule`, {
        method: "POST",
        body: {
          start_at: new Date(start).toISOString(),
          end_at: new Date(end).toISOString(),
          timezone,
        },
      });
      onScheduled(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not schedule exam.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open
      onClose={onClose}
      title="Schedule exam"
      actions={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" form="schedule-form" loading={busy} disabled={!start || !end}>
            Schedule
          </Button>
        </>
      }
    >
      <form id="schedule-form" className="stack gap-4" onSubmit={submit}>
        <p className="muted text-sm">Times are entered in your local timezone and stored in UTC.</p>
        <Field label="Start">
          <Input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} aria-label="Start time" required />
        </Field>
        <Field label="End">
          <Input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} aria-label="End time" required />
        </Field>
        {error && <Alert tone="error">{error}</Alert>}
      </form>
    </Dialog>
  );
}
