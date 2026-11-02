"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StudentShell } from "@/components/StudentShell";
import { Icon } from "@/components/icons";
import { Alert, Badge, Card, LoadingState } from "@/components/ui";

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
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load result."))
      .finally(() => setLoading(false));
  }, [params.attemptId]);

  const right = (
    <Link href="/student" className="btn btn-secondary btn-sm">
      <Icon.ChevronLeft size={16} /> Dashboard
    </Link>
  );

  const pct = result && result.total_marks > 0 ? Math.round((result.awarded_marks / result.total_marks) * 100) : null;

  return (
    <StudentShell right={right} maxWidth={820}>
      <div style={{ marginBottom: "var(--s-6)" }}>
        <span className="badge badge-accent">Exam result</span>
        <h1 className="page-title" style={{ marginTop: "var(--s-3)" }}>
          Your result
        </h1>
      </div>

      {loading && <LoadingState label="Loading result…" />}
      {error && <Alert tone="error">{error}</Alert>}

      {result && (
        <div className="stack gap-6">
          <Card className="row between wrap gap-4" style={{ alignItems: "center" }}>
            <div>
              <p className="muted text-sm">
                Exam #{result.exam_id} · Attempt #{result.attempt_id}
              </p>
              <div style={{ fontSize: "var(--text-3xl)", fontWeight: 750, marginTop: "var(--s-2)" }}>
                {result.awarded_marks}
                <span className="muted" style={{ fontSize: "var(--text-lg)", fontWeight: 500 }}>
                  {" "}
                  / {result.total_marks} marks
                </span>
              </div>
            </div>
            {pct != null && (
              <div
                style={{
                  display: "grid",
                  placeItems: "center",
                  width: 92,
                  height: 92,
                  borderRadius: "50%",
                  background: `conic-gradient(var(--indigo-500) ${pct * 3.6}deg, var(--grey-150) 0deg)`,
                }}
              >
                <div style={{ width: 70, height: 70, borderRadius: "50%", background: "var(--bg-surface)", display: "grid", placeItems: "center", fontWeight: 750 }}>
                  {pct}%
                </div>
              </div>
            )}
          </Card>

          <Card pad={false}>
            <div className="card-header">
              <span className="card-title">Per-question breakdown</span>
            </div>
            <div className="card-pad grid grid-stats">
              {result.questions.map((question, index) => (
                <div
                  key={question.version_id}
                  className="stat"
                  style={{ gap: "var(--s-2)" }}
                >
                  <span className="stat-label">Question {index + 1}</span>
                  <span style={{ fontSize: "var(--text-lg)", fontWeight: 700 }} className="tabular">
                    {question.awarded} / {question.marks}
                  </span>
                  <Badge tone={question.correct === null ? "neutral" : question.correct ? "success" : "danger"} dot>
                    {question.correct === null ? "Reviewed" : question.correct ? "Correct" : "Incorrect"}
                  </Badge>
                </div>
              ))}
            </div>
          </Card>

          <Alert tone="info">
            Correct answers and explanations are not shown here. For questions or grading concerns,
            contact your institution.
          </Alert>

          <div>
            <Link href="/student" className="btn btn-primary">
              Back to dashboard
            </Link>
          </div>
        </div>
      )}
    </StudentShell>
  );
}
