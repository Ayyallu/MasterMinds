"use client";

import { Badge, Card, Stat, StatusBadge, Table } from "./ui";
import { Icon } from "./icons";

export type ExamReport = {
  exam_id: number;
  participants: number;
  completed: number;
  score_distribution: number[];
  rows: { student_user_id: number; status: string; awarded_marks: number | null; total_marks: number | null }[];
};

/** Renders an exam report: summary stats, score distribution and per-student rows. */
export function ReportView({ report }: { report: ExamReport }) {
  const dist = report.score_distribution ?? [];
  const maxBar = Math.max(1, ...dist);
  const bucketCount = dist.length;
  const completionRate =
    report.participants > 0 ? Math.round((report.completed / report.participants) * 100) : 0;

  return (
    <div className="stack gap-6">
      <div className="grid grid-stats">
        <Stat label="Participants" value={report.participants} icon={<Icon.Users size={18} />} />
        <Stat label="Completed" value={report.completed} icon={<Icon.ClipboardCheck size={18} />} foot={`${completionRate}% completion`} />
        <Stat label="Score buckets" value={bucketCount} icon={<Icon.Chart size={18} />} />
      </div>

      <Card>
        <div className="row between" style={{ marginBottom: "var(--s-4)" }}>
          <span className="card-title">Score distribution</span>
          <Badge tone="accent">by bucket</Badge>
        </div>
        {dist.length === 0 || dist.every((v) => v === 0) ? (
          <p className="muted text-sm">No scored attempts to chart yet.</p>
        ) : (
          <div
            role="img"
            aria-label={`Score distribution across ${bucketCount} buckets`}
            style={{
              display: "grid",
              gridTemplateColumns: `repeat(${bucketCount}, 1fr)`,
              alignItems: "end",
              gap: "var(--s-2)",
              height: 180,
            }}
          >
            {dist.map((count, i) => (
              <div key={i} className="stack gap-2" style={{ justifyContent: "flex-end", height: "100%" }}>
                <div style={{ display: "grid", alignItems: "end", height: "100%" }}>
                  <div
                    title={`Bucket ${i + 1}: ${count}`}
                    style={{
                      height: `${(count / maxBar) * 100}%`,
                      minHeight: count > 0 ? 4 : 0,
                      background: "linear-gradient(180deg, var(--indigo-500), var(--navy-600))",
                      borderRadius: "var(--r-xs) var(--r-xs) 0 0",
                      transition: "height var(--dur) var(--ease)",
                    }}
                  />
                </div>
                <span className="text-xs muted tabular" style={{ textAlign: "center" }}>
                  {count}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card pad={false}>
        <div className="card-header">
          <span className="card-title">Per-student results</span>
        </div>
        {report.rows.length === 0 ? (
          <p className="muted text-sm card-pad">No participants yet.</p>
        ) : (
          <Table columns={["Student ID", "Status", "Awarded", "Total", "%"]}>
            {report.rows.map((r) => {
              const pct =
                r.awarded_marks != null && r.total_marks
                  ? Math.round((r.awarded_marks / r.total_marks) * 100)
                  : null;
              return (
                <tr key={r.student_user_id}>
                  <td className="mono">#{r.student_user_id}</td>
                  <td>
                    <StatusBadge status={r.status} />
                  </td>
                  <td className="tabular">{r.awarded_marks ?? "—"}</td>
                  <td className="tabular">{r.total_marks ?? "—"}</td>
                  <td className="tabular">{pct != null ? `${pct}%` : "—"}</td>
                </tr>
              );
            })}
          </Table>
        )}
      </Card>
    </div>
  );
}
