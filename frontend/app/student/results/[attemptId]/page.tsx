"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import "../../student.css";

type Result = {
  attempt_id: number;
  exam_id: number;
  total_marks: number;
  awarded_marks: number;
  questions: { version_id: number; marks: number; awarded: number; correct: boolean | null }[];
};

export default function StudentResultPage() {
  const params = useParams<{ attemptId: string }>();
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Result>(`/attempts/${params.attemptId}/result`)
      .then(setResult)
      .catch(err => setError(err instanceof Error ? err.message : "Could not load result."))
      .finally(() => setLoading(false));
  }, [params.attemptId]);

  return (
    <main className="student-shell">
      <div className="student-topbar">
        <Link className="student-brand" href="/student">MasterMinds</Link>
        <Link className="student-button secondary" href="/student">Back to dashboard</Link>
      </div>
      <section className="student-card">
        <p className="student-pill">EXAM RESULT</p>
        <h1>Your result</h1>
        {loading && <p className="student-muted">Loading result…</p>}
        {error && <p className="student-error" role="alert">{error}</p>}
        {result && (
          <>
            <p className="student-muted">Exam #{result.exam_id} · Attempt #{result.attempt_id}</p>
            <p style={{ fontSize: "2.4rem", fontWeight: 800, margin: ".75rem 0" }}>
              {result.awarded_marks} <span className="student-muted" style={{ fontSize: "1.1rem", fontWeight: 500 }}>/ {result.total_marks} marks</span>
            </p>
            <div className="student-grid" style={{ marginTop: "1.5rem" }}>
              {result.questions.map((question, index) => (
                <div className="student-card" key={question.version_id}>
                  <strong>Question {index + 1}</strong>
                  <p>{question.awarded} / {question.marks} marks</p>
                  <span className="student-pill">{question.correct === null ? "Reviewed" : question.correct ? "Correct" : "Incorrect"}</span>
                </div>
              ))}
            </div>
            <p className="student-muted" style={{ marginTop: "1.25rem" }}>For exam questions or grading concerns, contact your institution. Correct answers and answer explanations are not shown in this result view.</p>
          </>
        )}
      </section>
    </main>
  );
}
