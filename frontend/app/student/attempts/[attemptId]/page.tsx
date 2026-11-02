"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { api, clearTokens, getToken } from "@/lib/api";
import { Icon } from "@/components/icons";
import { Alert, Badge, Button, Card, ConfirmDialog, LoadingState, Spinner } from "@/components/ui";
import "../../exam.css";

type Question = {
  question_version_id: number;
  type: string;
  text: string;
  marks: number;
  options: { id: number; text: string }[];
  answer: { selected_option_ids?: number[]; numerical_value?: string } | null;
};
type Attempt = {
  id: number;
  exam_id: number;
  status: string;
  attempt_no: number;
  started_at: string;
  deadline_at: string;
  submitted_at: string | null;
  seconds_remaining: number;
  questions: Question[];
};
type Answer = { selected_option_ids?: number[]; numerical_value?: string };

function formatTime(seconds: number) {
  const s = Math.max(0, seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const mm = m.toString().padStart(2, "0");
  const ss = sec.toString().padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

function isAnswered(a: Answer | undefined): boolean {
  if (!a) return false;
  if (a.selected_option_ids && a.selected_option_ids.length > 0) return true;
  if (a.numerical_value != null && a.numerical_value.trim() !== "") return true;
  return false;
}

export default function StudentAttemptPage() {
  const params = useParams<{ attemptId: string }>();
  const attemptId = params.attemptId;
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [answers, setAnswers] = useState<Record<number, Answer>>({});
  const [remaining, setRemaining] = useState(0);
  const [current, setCurrent] = useState(0);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [saveState, setSaveState] = useState<"saved" | "saving" | "failed" | "submitting" | "submitted">("saved");
  const [error, setError] = useState<string | null>(null);
  const submittedRef = useRef(false);
  const answersRef = useRef<Record<number, Answer>>({});

  useEffect(() => {
    answersRef.current = answers;
  }, [answers]);

  const loadAttempt = useCallback(async () => {
    if (!getToken()) {
      setError("Please sign in to continue.");
      setLoading(false);
      return;
    }
    try {
      const data = await api<Attempt>(`/attempts/${attemptId}`);
      setAttempt(data);
      setRemaining(data.seconds_remaining);
      const restored: Record<number, Answer> = {};
      for (const question of data.questions) {
        if (question.answer) restored[question.question_version_id] = question.answer;
      }
      setAnswers(restored);
      if (data.status !== "in_progress") submittedRef.current = true;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not load this attempt.";
      if (message.toLowerCase().includes("token")) clearTokens();
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [attemptId]);

  useEffect(() => {
    void loadAttempt();
  }, [loadAttempt]);

  const submitAttempt = useCallback(
    async (automatic = false) => {
      if (submittedRef.current || submitting) return;
      submittedRef.current = true;
      setSubmitting(true);
      setError(null);
      setSaveState("submitting");
      try {
        // Flush the latest in-memory answers before submitting so a click just
        // after a selection cannot race the debounced autosave.
        for (const [questionId, answer] of Object.entries(answersRef.current)) {
          try {
            await api(`/attempts/${attemptId}/answers/${questionId}`, {
              method: "PUT",
              body: answer,
            });
          } catch (err) {
            if (!automatic) throw err;
          }
        }
        const data = await api<Attempt>(`/attempts/${attemptId}/submit`, { method: "POST" });
        setAttempt(data);
        setRemaining(0);
        setSaveState("submitted");
      } catch (err) {
        submittedRef.current = false;
        setError(err instanceof Error ? err.message : "Submission failed. Please try again.");
        setSaveState("failed");
      } finally {
        setSubmitting(false);
      }
    },
    [attemptId, submitting],
  );

  useEffect(() => {
    if (!attempt || attempt.status !== "in_progress") return;
    const deadlineMs = Date.parse(attempt.deadline_at);
    const tick = () => {
      const seconds = Math.max(0, Math.ceil((deadlineMs - Date.now()) / 1000));
      setRemaining(seconds);
      if (seconds <= 0) {
        window.clearInterval(timer);
        void submitAttempt(true);
      }
    };
    const timer = window.setInterval(tick, 1000);
    tick();
    return () => window.clearInterval(timer);
  }, [attempt, submitAttempt]);

  useEffect(() => {
    if (!attempt || attempt.status !== "in_progress") return;
    const ids = Object.keys(answers);
    if (ids.length === 0) return;
    setSaveState("saving");
    const timer = window.setTimeout(async () => {
      try {
        for (const key of ids) {
          const questionId = Number(key);
          await api(`/attempts/${attempt.id}/answers/${questionId}`, {
            method: "PUT",
            body: answers[questionId],
          });
        }
        setSaveState("saved");
      } catch (err) {
        setSaveState("failed");
        setError(err instanceof Error ? err.message : "Could not save an answer.");
      }
    }, 450);
    return () => window.clearTimeout(timer);
  }, [answers, attempt]);

  // Guard against accidental navigation while the exam is in progress.
  useEffect(() => {
    if (!attempt || attempt.status !== "in_progress") return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [attempt]);

  function setQuestionAnswer(questionId: number, answer: Answer) {
    const next = { ...answersRef.current, [questionId]: answer };
    answersRef.current = next;
    setAnswers(next);
    setError(null);
  }

  if (loading) {
    return (
      <div style={{ display: "grid", placeItems: "center", minHeight: "100vh" }}>
        <LoadingState label="Loading exam…" />
      </div>
    );
  }
  if (!attempt) {
    return (
      <div style={{ maxWidth: 520, margin: "10vh auto", padding: "0 var(--s-4)" }}>
        <Card className="stack gap-4">
          <h1>Unable to open exam</h1>
          {error && <Alert tone="error">{error}</Alert>}
          <Link href="/student" className="btn btn-primary" style={{ width: "fit-content" }}>
            Back to student portal
          </Link>
        </Card>
      </div>
    );
  }

  const isOpen = attempt.status === "in_progress";
  const questions = attempt.questions;
  const answeredCount = questions.filter((q) => isAnswered(answers[q.question_version_id])).length;
  const total = questions.length;
  const q = questions[Math.min(current, Math.max(0, total - 1))];

  if (!isOpen) {
    return (
      <div style={{ maxWidth: 560, margin: "8vh auto", padding: "0 var(--s-4)" }}>
        <Card className="stack gap-4" style={{ textAlign: "center" }}>
          <span className="state-icon" style={{ margin: "0 auto", background: "var(--success-50)", color: "var(--success-500)", width: 56, height: 56 }}>
            <Icon.CheckCircle size={28} />
          </span>
          <h1>Exam submitted</h1>
          <p className="muted">
            Your attempt has been submitted successfully. Return to your dashboard to see whether
            results have been released.
          </p>
          <Link href="/student" className="btn btn-primary" style={{ margin: "0 auto" }}>
            Back to dashboard
          </Link>
        </Card>
      </div>
    );
  }

  if (total === 0 || !q) {
    return (
      <div style={{ maxWidth: 520, margin: "10vh auto", padding: "0 var(--s-4)" }}>
        <Card className="stack gap-4">
          <h1>No questions available</h1>
          <p className="muted">This attempt has no questions to display. Please contact your institution.</p>
          <Link href="/student" className="btn btn-primary" style={{ width: "fit-content" }}>
            Back to dashboard
          </Link>
        </Card>
      </div>
    );
  }

  const timerClass = remaining <= 60 ? "danger" : remaining <= 300 ? "warn" : "";

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-app)" }}>
      <header className="exam-header">
        <div className="exam-header-inner">
          <div className="stack">
            <span className="brand" style={{ fontSize: "var(--text-md)" }}>
              <span className="sidebar-logo" style={{ width: 26, height: 26 }}>
                <Icon.GraduationCap size={16} />
              </span>
              Exam in progress
            </span>
            <span className="muted text-xs">Attempt {attempt.attempt_no}</span>
          </div>
          <div className="row gap-4 wrap">
            <span className={`save-status`} aria-live="polite">
              {saveState === "saving" ? (
                <>
                  <Spinner /> Saving…
                </>
              ) : saveState === "failed" ? (
                <span style={{ color: "var(--danger-700)" }} className="row gap-1">
                  <Icon.AlertCircle size={14} /> Save failed
                </span>
              ) : (
                <span className="row gap-1" style={{ color: "var(--success-700)" }}>
                  <Icon.CheckCircle size={14} /> All changes saved
                </span>
              )}
            </span>
            <span className={`exam-timer ${timerClass}`} aria-live="polite" role="timer">
              <Icon.Clock size={18} /> {formatTime(remaining)}
            </span>
          </div>
        </div>
      </header>

      {error && (
        <div style={{ maxWidth: 1120, margin: "var(--s-4) auto 0", padding: "0 var(--s-6)" }}>
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      <div className="exam-body">
        <div className="stack gap-5">
          <Card className="stack gap-4">
            <div className="row between wrap gap-2">
              <span className="section-title">
                Question {current + 1} of {total}
              </span>
              <Badge tone="neutral">
                {q.marks} mark{q.marks === 1 ? "" : "s"}
              </Badge>
            </div>
            <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.65, fontSize: "var(--text-md)", margin: 0 }}>{q.text}</p>

            {q.type === "numerical" ? (
              <div className="field" style={{ maxWidth: 320 }}>
                <label className="label">Your numerical answer</label>
                <input
                  className="input"
                  inputMode="decimal"
                  value={answers[q.question_version_id]?.numerical_value ?? ""}
                  onChange={(e) => setQuestionAnswer(q.question_version_id, { numerical_value: e.target.value })}
                  aria-label="Numerical answer"
                />
              </div>
            ) : (
              <div className="stack gap-2">
                {q.options.map((option) => {
                  const selected = answers[q.question_version_id]?.selected_option_ids ?? [];
                  const checked = selected.includes(option.id);
                  const multi = q.type === "multi_mcq";
                  return (
                    <label key={option.id} className={`exam-option ${checked ? "selected" : ""}`}>
                      <input
                        type={multi ? "checkbox" : "radio"}
                        name={`question-${q.question_version_id}`}
                        checked={checked}
                        onChange={() => {
                          if (multi) {
                            const next = checked ? selected.filter((id) => id !== option.id) : [...selected, option.id];
                            setQuestionAnswer(q.question_version_id, { selected_option_ids: next });
                          } else {
                            setQuestionAnswer(q.question_version_id, { selected_option_ids: [option.id] });
                          }
                        }}
                      />
                      <span>{option.text}</span>
                    </label>
                  );
                })}
              </div>
            )}
          </Card>

          <div className="row between wrap gap-3">
            <Button variant="secondary" disabled={current === 0} onClick={() => setCurrent((c) => Math.max(0, c - 1))} icon={<Icon.ChevronLeft size={16} />}>
              Previous
            </Button>
            {current < total - 1 ? (
              <Button onClick={() => setCurrent((c) => Math.min(total - 1, c + 1))}>
                Next <Icon.ChevronRight size={16} />
              </Button>
            ) : (
              <Button variant="success" icon={<Icon.Check size={16} />} onClick={() => setConfirmOpen(true)}>
                Review & submit
              </Button>
            )}
          </div>
        </div>

        <aside className="exam-palette">
          <Card className="stack gap-4">
            <div className="row between">
              <span className="section-title">Questions</span>
              <Badge tone="accent">
                {answeredCount}/{total}
              </Badge>
            </div>
            <div className="palette-grid">
              {questions.map((question, i) => {
                const answered = isAnswered(answers[question.question_version_id]);
                return (
                  <button
                    key={question.question_version_id}
                    className={`palette-btn ${answered ? "answered" : ""} ${i === current ? "current" : ""}`}
                    onClick={() => setCurrent(i)}
                    aria-label={`Question ${i + 1}${answered ? ", answered" : ", not answered"}`}
                    aria-current={i === current}
                  >
                    {i + 1}
                  </button>
                );
              })}
            </div>
            <div className="stack gap-2 text-xs muted">
              <span className="row gap-2">
                <span className="palette-btn answered" style={{ width: 16, height: 16, aspectRatio: "auto" }} /> Answered
              </span>
              <span className="row gap-2">
                <span className="palette-btn" style={{ width: 16, height: 16, aspectRatio: "auto" }} /> Not answered
              </span>
            </div>
            <Button block variant="success" icon={<Icon.Check size={16} />} onClick={() => setConfirmOpen(true)}>
              Submit exam
            </Button>
            <p className="text-xs muted" style={{ margin: 0, textAlign: "center" }}>
              Answers save automatically.
            </p>
          </Card>
        </aside>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={() => {
          setConfirmOpen(false);
          void submitAttempt(false);
        }}
        title="Submit your exam?"
        message={
          answeredCount < total
            ? `You have answered ${answeredCount} of ${total} questions. ${total - answeredCount} unanswered question(s) will be submitted blank. Once submitted, you cannot change your answers.`
            : `You have answered all ${total} questions. Once submitted, you cannot change your answers.`
        }
        confirmLabel="Submit exam"
        tone="success"
        loading={submitting}
      />
    </div>
  );
}
