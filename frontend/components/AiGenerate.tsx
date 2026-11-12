"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Icon } from "./icons";
import {
  Alert,
  Button,
  Card,
  CardHeader,
  Field,
  Input,
  Select,
  Stat,
  StatusBadge,
  useToast,
} from "./ui";

type AiStatus = { provider: string; model: string; configured: boolean };

/** Max pool size per request — mirrors the backend's AI_MAX_POOL_SIZE default. */
const MAX_COUNT = 50;

export type Job = {
  id: number;
  status: string;
  provider: string;
  model: string | null;
  is_global: boolean;
  requested_count: number;
  stored_count: number;
  rejected_count: number;
  duplicate_count: number;
  error: string | null;
  usage: Record<string, unknown> | null;
};

/** Reusable AI generation form (private or global). */
export function GenerateForm({
  endpoint,
  global,
  onJob,
}: {
  endpoint: string;
  global?: boolean;
  onJob: (job: Job) => void;
}) {
  const toast = useToast();
  const [questionType, setQuestionType] = useState("single_mcq");
  const [count, setCount] = useState(5);
  const [difficulty, setDifficulty] = useState("medium");
  const [subject, setSubject] = useState("");
  const [grade, setGrade] = useState("");
  const [topics, setTopics] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<AiStatus | null>(null);

  useEffect(() => {
    api<AiStatus>("/ai/status").then(setStatus).catch(() => setStatus(null));
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = {
        question_type: questionType,
        count,
        difficulty,
        subject: subject.trim() || null,
        grade: grade.trim() || null,
        topics: topics.split(",").map((t) => t.trim()).filter(Boolean),
        idempotency_key: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      };
      const job = await api<Job>(endpoint, { method: "POST", body });
      onJob(job);
      if (job.status === "failed") {
        setError(job.error ?? "Generation failed.");
        toast.push("AI generation failed.", "error");
      } else if (job.stored_count === 0) {
        toast.push("No usable questions were produced — see the job details.", "info");
      } else {
        toast.push(`Generated ${job.stored_count} candidate${job.stored_count === 1 ? "" : "s"}.`, "success");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card pad={false}>
      <CardHeader title={global ? "Generate global candidates" : "Generate candidates"} action={<Icon.Sparkles size={18} />} />
      <form className="card-pad stack gap-4" onSubmit={submit}>
        <div className="row gap-3 wrap">
          <Field label="Question type">
            <Select value={questionType} onChange={(e) => setQuestionType(e.target.value)} aria-label="Question type">
              <option value="single_mcq">Single choice</option>
              <option value="multi_mcq">Multi select</option>
              <option value="true_false">True / False</option>
              <option value="numerical">Numerical</option>
            </Select>
          </Field>
          <Field label="Count" hint={`1–${MAX_COUNT}`}>
            <Input type="number" min={1} max={MAX_COUNT} value={count} onChange={(e) => setCount(Math.min(MAX_COUNT, Math.max(1, Number(e.target.value) || 1)))} aria-label="Count" style={{ width: 100 }} />
          </Field>
          <Field label="Difficulty">
            <Select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} aria-label="Difficulty">
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </Select>
          </Field>
        </div>
        <div className="row gap-3 wrap">
          <Field label="Subject (optional)">
            <Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="e.g. Physics" aria-label="Subject" />
          </Field>
          <Field label="Grade (optional)">
            <Input value={grade} onChange={(e) => setGrade(e.target.value)} placeholder="e.g. Grade 10" aria-label="Grade" />
          </Field>
        </div>
        <Field label="Topics (optional)" hint="Comma-separated.">
          <Input value={topics} onChange={(e) => setTopics(e.target.value)} placeholder="Kinematics, Newton's laws" aria-label="Topics" />
        </Field>
        {status && status.provider === "mock" && (
          <Alert tone="warning">
            Demo mode: the built-in <strong>mock</strong> generator is active, so questions are placeholders. Set{" "}
            <code>AI_PROVIDER=nvidia</code> and <code>NVIDIA_API_KEY</code> in <code>backend/.env</code> and restart the backend to use real AI.
          </Alert>
        )}
        {status && status.provider !== "mock" && !status.configured && (
          <Alert tone="error">
            The AI provider is <strong>{status.provider}</strong> but no API key is configured on the server.
          </Alert>
        )}
        {status && status.provider !== "mock" && status.configured && (
          <p className="muted text-sm row gap-2">
            <Icon.Sparkles size={14} /> Using <strong className="strong">{status.provider}</strong> · <span className="mono">{status.model}</span>
            {count > 10 && <> — large pools take a minute or more.</>}
          </p>
        )}
        <Alert tone="info">
          Candidates are validated, de-duplicated and stored as <strong>in&nbsp;review</strong>. No student
          data is sent to the provider. Nothing is generated during a live exam.
        </Alert>
        {error && <Alert tone="error">{error}</Alert>}
        <div>
          <Button type="submit" icon={<Icon.Sparkles size={16} />} loading={busy}>
            Generate
          </Button>
        </div>
      </form>
    </Card>
  );
}

export function JobResult({ job, reviewHref }: { job: Job; reviewHref: string }) {
  return (
    <Card pad={false}>
      <CardHeader title={`Generation job #${job.id}`} action={<StatusBadge status={job.status} />} />
      <div className="card-pad stack gap-4">
        <div className="grid grid-stats">
          <Stat label="Stored" value={job.stored_count} icon={<Icon.CheckCircle size={18} />} />
          <Stat label="Duplicates" value={job.duplicate_count} icon={<Icon.Layers size={18} />} />
          <Stat label="Rejected" value={job.rejected_count} icon={<Icon.AlertCircle size={18} />} />
          <Stat label="Requested" value={job.requested_count} icon={<Icon.Sparkles size={18} />} />
        </div>
        <p className="muted text-sm">
          Provider: <strong className="strong">{job.provider}</strong>
          {job.model ? ` · ${job.model}` : ""}
        </p>
        {job.error && <Alert tone="error">{job.error}</Alert>}
        {job.stored_count > 0 && reviewHref !== "#" && (
          <div>
            <Link href={reviewHref} className="btn btn-secondary btn-sm">
              Review new candidates <Icon.ArrowRight size={16} />
            </Link>
          </div>
        )}
      </div>
    </Card>
  );
}
