"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Icon } from "./icons";
import { Alert, Button, Dialog, Field, Input, Select } from "./ui";

type Rule = { count: number; type: string; difficulty: string };
type ExamOut = { id: number; title: string; status: string };

/** Create-exam dialog. Returns the created exam via onCreated. */
export function ExamForm({
  institutionId,
  onClose,
  onCreated,
}: {
  institutionId: number;
  onClose: () => void;
  onCreated: (exam: ExamOut) => void;
}) {
  const [title, setTitle] = useState("");
  const [duration, setDuration] = useState(60);
  const [attemptLimit, setAttemptLimit] = useState(1);
  const [randomize, setRandomize] = useState(true);
  const [negative, setNegative] = useState(false);
  const [release, setRelease] = useState("manual");
  const [rules, setRules] = useState<Rule[]>([{ count: 10, type: "", difficulty: "" }]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const distribution = rules.map((r) => ({
        count: r.count,
        ...(r.type ? { type: r.type } : {}),
        ...(r.difficulty ? { difficulty: r.difficulty } : {}),
      }));
      const exam = await api<ExamOut>(`/institutions/${institutionId}/exams`, {
        method: "POST",
        body: {
          title: title.trim(),
          duration_minutes: duration,
          attempt_limit: attemptLimit,
          randomize,
          negative_marking: negative,
          result_release_rule: release,
          timezone: "UTC",
          distribution,
        },
      });
      onCreated(exam);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create exam.");
    } finally {
      setBusy(false);
    }
  }

  const totalQuestions = rules.reduce((n, r) => n + (r.count || 0), 0);

  return (
    <Dialog
      open
      onClose={onClose}
      title="Create exam"
      actions={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" form="exam-form" loading={busy}>
            Create draft
          </Button>
        </>
      }
    >
      <form id="exam-form" className="stack gap-4" onSubmit={submit}>
        <Field label="Exam title">
          <Input required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Physics — Unit 1 Test" aria-label="Exam title" />
        </Field>
        <div className="row gap-3 wrap">
          <Field label="Duration (min)">
            <Input type="number" min={1} value={duration} onChange={(e) => setDuration(Math.max(1, Number(e.target.value) || 1))} aria-label="Duration minutes" style={{ width: 120 }} />
          </Field>
          <Field label="Attempt limit">
            <Input type="number" min={1} value={attemptLimit} onChange={(e) => setAttemptLimit(Math.max(1, Number(e.target.value) || 1))} aria-label="Attempt limit" style={{ width: 120 }} />
          </Field>
          <Field label="Result release">
            <Select value={release} onChange={(e) => setRelease(e.target.value)} aria-label="Result release rule">
              <option value="manual">Manual</option>
              <option value="after_close">After close</option>
            </Select>
          </Field>
        </div>

        <Field label={`Blueprint — ${totalQuestions} question${totalQuestions === 1 ? "" : "s"}`} hint="Each rule draws approved questions matching its filters.">
          <div className="stack gap-2">
            {rules.map((r, i) => (
              <div key={i} className="row gap-2 wrap">
                <Input
                  type="number"
                  min={1}
                  value={r.count}
                  onChange={(e) => setRules((p) => p.map((x, idx) => (idx === i ? { ...x, count: Math.max(1, Number(e.target.value) || 1) } : x)))}
                  aria-label={`Rule ${i + 1} count`}
                  style={{ width: 80 }}
                />
                <Select
                  value={r.type}
                  onChange={(e) => setRules((p) => p.map((x, idx) => (idx === i ? { ...x, type: e.target.value } : x)))}
                  aria-label={`Rule ${i + 1} type`}
                  style={{ width: 150 }}
                >
                  <option value="">Any type</option>
                  <option value="single_mcq">Single choice</option>
                  <option value="multi_mcq">Multi select</option>
                  <option value="true_false">True / False</option>
                  <option value="numerical">Numerical</option>
                </Select>
                <Select
                  value={r.difficulty}
                  onChange={(e) => setRules((p) => p.map((x, idx) => (idx === i ? { ...x, difficulty: e.target.value } : x)))}
                  aria-label={`Rule ${i + 1} difficulty`}
                  style={{ width: 130 }}
                >
                  <option value="">Any level</option>
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </Select>
                {rules.length > 1 && (
                  <Button type="button" variant="ghost" size="sm" className="btn-icon" aria-label="Remove rule" onClick={() => setRules((p) => p.filter((_, idx) => idx !== i))}>
                    <Icon.Close size={16} />
                  </Button>
                )}
              </div>
            ))}
            <div>
              <Button type="button" variant="ghost" size="sm" icon={<Icon.Plus size={16} />} onClick={() => setRules((p) => [...p, { count: 5, type: "", difficulty: "" }])}>
                Add rule
              </Button>
            </div>
          </div>
        </Field>

        <div className="row gap-4 wrap">
          <label className="row gap-2 text-sm">
            <input type="checkbox" checked={randomize} onChange={(e) => setRandomize(e.target.checked)} /> Randomize per student
          </label>
          <label className="row gap-2 text-sm">
            <input type="checkbox" checked={negative} onChange={(e) => setNegative(e.target.checked)} /> Negative marking
          </label>
        </div>

        {error && <Alert tone="error">{error}</Alert>}
      </form>
    </Dialog>
  );
}
