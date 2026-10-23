"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { api, clearTokens, getToken } from "@/lib/api";
import "../../student.css";

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
  const mins = Math.floor(Math.max(0, seconds) / 60).toString().padStart(2, "0");
  const secs = (Math.max(0, seconds) % 60).toString().padStart(2, "0");
  return `${mins}:${secs}`;
}

export default function StudentAttemptPage() {
  const params = useParams<{ attemptId: string }>();
  const attemptId = params.attemptId;
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [answers, setAnswers] = useState<Record<number, Answer>>({});
  const [remaining, setRemaining] = useState(0);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [saveState, setSaveState] = useState("All changes saved");
  const [error, setError] = useState<string | null>(null);
  const submittedRef = useRef(false);
  const answersRef = useRef<Record<number, Answer>>({});

  useEffect(() => { answersRef.current = answers; }, [answers]);

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

  useEffect(() => { void loadAttempt(); }, [loadAttempt]);

  const submitAttempt = useCallback(async (automatic = false) => {
    if (submittedRef.current || submitting) return;
    submittedRef.current = true;
    setSubmitting(true);
    setError(null);
    setSaveState(automatic ? "Time expired — submitting…" : "Submitting exam…");
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
      setSaveState("Exam submitted");
    } catch (err) {
      submittedRef.current = false;
      setError(err instanceof Error ? err.message : "Submission failed. Please try again.");
      setSaveState("Submission needs attention");
    } finally {
      setSubmitting(false);
    }
  }, [attemptId, submitting]);

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
    setSaveState("Saving answers…");
    const timer = window.setTimeout(async () => {
      try {
        for (const key of ids) {
          const questionId = Number(key);
          await api(`/attempts/${attempt.id}/answers/${questionId}`, {
            method: "PUT",
            body: answers[questionId],
          });
        }
        setSaveState("All changes saved");
      } catch (err) {
        setSaveState("Save failed — check your connection");
        setError(err instanceof Error ? err.message : "Could not save an answer.");
      }
    }, 450);
    return () => window.clearTimeout(timer);
  }, [answers, attempt]);

  function setQuestionAnswer(questionId: number, answer: Answer) {
    const next = { ...answersRef.current, [questionId]: answer };
    answersRef.current = next;
    setAnswers(next);
    setError(null);
  }

  if (loading) return <main className="student-shell"><p className="student-muted">Loading exam…</p></main>;
  if (!attempt) return (
    <main className="student-shell">
      <h1>Unable to open exam</h1>
      {error && <p className="student-error" role="alert">{error}</p>}
      <Link className="student-button" href="/student">Back to student portal</Link>
    </main>
  );

  const isOpen = attempt.status === "in_progress";
  return (
    <main className="student-shell">
      <div className="student-topbar">
        <Link className="student-brand" href="/student">MasterMinds</Link>
        <div style={{ textAlign: "right" }}>
          <div className="student-timer" aria-live="polite">Time remaining: {formatTime(remaining)}</div>
          <div className="student-muted" style={{ fontSize: ".85rem" }}>{saveState}</div>
        </div>
      </div>
      <section className="student-card">
        <p className="student-pill">{isOpen ? "EXAM IN PROGRESS" : "ATTEMPT SUBMITTED"}</p>
        <h1>Exam attempt</h1>
        <p className="student-muted">Attempt {attempt.attempt_no} · Started {new Date(attempt.started_at).toLocaleString()}</p>
        {!isOpen && <div className="student-success" role="status">Your exam has been submitted. You can return to the dashboard to see whether results have been released.</div>}
      </section>
      {error && <p className="student-error" role="alert">{error}</p>}
      {attempt.questions.map((question, index) => {
        const answer = answers[question.question_version_id] ?? {};
        const selected = answer.selected_option_ids ?? [];
        return (
          <section className="student-question" key={question.question_version_id}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem" }}>
              <strong>Question {index + 1}</strong>
              <span className="student-pill">{question.marks} mark{question.marks === 1 ? "" : "s"}</span>
            </div>
            <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.6 }}>{question.text}</p>
            {question.type === "numerical" ? (
              <label className="student-label" style={{ maxWidth: 320 }}>Your numerical answer
                <input className="student-input" inputMode="decimal" disabled={!isOpen} value={answer.numerical_value ?? ""} onChange={e => setQuestionAnswer(question.question_version_id, { numerical_value: e.target.value })} />
              </label>
            ) : (
              <div>
                {question.options.map(option => {
                  const checked = selected.includes(option.id);
                  const multi = question.type === "multi_mcq";
                  return (
                    <label className="student-option" key={option.id}>
                      <input
                        type={multi ? "checkbox" : "radio"}
                        name={`question-${question.question_version_id}`}
                        disabled={!isOpen}
                        checked={checked}
                        onChange={() => {
                          if (multi) {
                            const next = checked ? selected.filter(id => id !== option.id) : [...selected, option.id];
                            setQuestionAnswer(question.question_version_id, { selected_option_ids: next });
                          } else {
                            setQuestionAnswer(question.question_version_id, { selected_option_ids: [option.id] });
                          }
                        }}
                      />
                      <span>{option.text}</span>
                    </label>
                  );
                })}
              </div>
            )}
          </section>
        );
      })}
      {isOpen ? (
        <div style={{ display: "flex", gap: ".8rem", flexWrap: "wrap", alignItems: "center", margin: "1.5rem 0" }}>
          <button className="student-button" disabled={submitting} onClick={() => void submitAttempt(false)}>{submitting ? "Submitting…" : "Submit exam"}</button>
          <span className="student-muted">Answers save automatically. Once submitted, you cannot change them.</span>
        </div>
      ) : (
        <p><Link className="student-button" href="/student">Return to dashboard</Link></p>
      )}
    </main>
  );
}
