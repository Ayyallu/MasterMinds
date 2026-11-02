"use client";

import { Badge, StatusBadge } from "./ui";
import { Icon } from "./icons";

export type QuestionOption = { id: number; text: string; order_index?: number; is_correct: boolean | null };
export type QuestionVersion = {
  question_id: number;
  version_id: number;
  version_no: number;
  type: string;
  text: string;
  explanation: string | null;
  difficulty: string;
  marks: number;
  status: string;
  options: QuestionOption[];
  numerical_answer: string | null;
  numerical_tolerance: string | null;
};

const TYPE_LABEL: Record<string, string> = {
  single_mcq: "Single choice",
  multi_mcq: "Multi select",
  true_false: "True / False",
  numerical: "Numerical",
};

const DIFF_TONE: Record<string, "success" | "warning" | "danger"> = {
  easy: "success",
  medium: "warning",
  hard: "danger",
};

/** Renders a serialized question version. Answer keys show only when present
    (staff serializer); student/preview serializers return null keys. */
export function QuestionCard({
  q,
  index,
  selectable,
  selected,
  onToggle,
}: {
  q: QuestionVersion;
  index?: number;
  selectable?: boolean;
  selected?: boolean;
  onToggle?: () => void;
}) {
  const showsKeys = q.options.some((o) => o.is_correct !== null) || q.numerical_answer != null;

  return (
    <div
      className="card card-pad stack gap-3"
      style={selected ? { borderColor: "var(--indigo-500)", boxShadow: "var(--shadow-focus)" } : undefined}
    >
      <div className="row between gap-3 wrap">
        <div className="row gap-2 wrap">
          {index != null && <Badge tone="neutral">Q{index + 1}</Badge>}
          <Badge tone="accent">{TYPE_LABEL[q.type] ?? q.type}</Badge>
          <Badge tone={DIFF_TONE[q.difficulty] ?? "neutral"}>{q.difficulty}</Badge>
          <Badge tone="neutral">{q.marks} mark{q.marks === 1 ? "" : "s"}</Badge>
          <Badge tone="neutral">v{q.version_no}</Badge>
          <StatusBadge status={q.status} />
        </div>
        {selectable && (
          <label className="row gap-2 text-sm" style={{ cursor: "pointer" }}>
            <input type="checkbox" checked={!!selected} onChange={onToggle} aria-label="Select question" />
            Select
          </label>
        )}
      </div>

      <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.6, margin: 0 }}>{q.text}</p>

      {q.type === "numerical" ? (
        <div className="muted text-sm">
          {showsKeys && q.numerical_answer != null ? (
            <span>
              <Icon.CheckCircle size={14} /> Answer: <strong className="strong">{q.numerical_answer}</strong>
              {q.numerical_tolerance ? ` (±${q.numerical_tolerance})` : ""}
            </span>
          ) : (
            <span className="faint">Numerical answer hidden</span>
          )}
        </div>
      ) : (
        <ul className="stack gap-2" style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {q.options.map((o) => {
            const correct = o.is_correct === true;
            return (
              <li
                key={o.id}
                className="row gap-2"
                style={{
                  padding: "var(--s-2) var(--s-3)",
                  borderRadius: "var(--r-sm)",
                  background: correct ? "var(--success-50)" : "var(--grey-50)",
                  border: correct ? "1px solid var(--success-200)" : "1px solid var(--border)",
                }}
              >
                {showsKeys &&
                  (correct ? (
                    <Icon.CheckCircle size={16} style={{ color: "var(--success-500)" }} />
                  ) : (
                    <span style={{ width: 16, flex: "none" }} />
                  ))}
                <span>{o.text}</span>
              </li>
            );
          })}
        </ul>
      )}

      {showsKeys && q.explanation && (
        <p className="muted text-sm" style={{ margin: 0 }}>
          <strong className="strong">Explanation:</strong> {q.explanation}
        </p>
      )}
    </div>
  );
}
