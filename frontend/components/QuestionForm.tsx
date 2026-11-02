"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Icon } from "./icons";
import { Alert, Button, Dialog, Field, Input, Select, Textarea } from "./ui";

type Opt = { text: string; is_correct: boolean };
type QType = "single_mcq" | "multi_mcq" | "true_false" | "numerical";

/** Authoring dialog for a new question (or a new version of an existing one). */
export function QuestionForm({
  institutionId,
  questionId,
  onClose,
  oncreated,
}: {
  institutionId: number;
  questionId?: number;
  onClose: () => void;
  oncreated: () => void;
}) {
  const [type, setType] = useState<QType>("single_mcq");
  const [text, setText] = useState("");
  const [explanation, setExplanation] = useState("");
  const [difficulty, setDifficulty] = useState("medium");
  const [marks, setMarks] = useState(1);
  const [options, setOptions] = useState<Opt[]>([
    { text: "", is_correct: true },
    { text: "", is_correct: false },
  ]);
  const [tfCorrect, setTfCorrect] = useState<"True" | "False">("True");
  const [numAnswer, setNumAnswer] = useState("");
  const [numTolerance, setNumTolerance] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function changeType(t: QType) {
    setType(t);
    setError(null);
    if (t === "single_mcq" || t === "multi_mcq") {
      setOptions([
        { text: "", is_correct: t === "single_mcq" },
        { text: "", is_correct: false },
      ]);
    }
  }

  function setCorrect(i: number) {
    if (type === "single_mcq") {
      setOptions((o) => o.map((opt, idx) => ({ ...opt, is_correct: idx === i })));
    } else {
      setOptions((o) => o.map((opt, idx) => (idx === i ? { ...opt, is_correct: !opt.is_correct } : opt)));
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);

    let body: Record<string, unknown> = {
      type,
      text: text.trim(),
      explanation: explanation.trim() || null,
      difficulty,
      marks,
    };

    if (type === "numerical") {
      body = { ...body, options: [], numerical_answer: numAnswer.trim(), numerical_tolerance: numTolerance.trim() || null };
    } else if (type === "true_false") {
      body = {
        ...body,
        options: [
          { text: "True", is_correct: tfCorrect === "True" },
          { text: "False", is_correct: tfCorrect === "False" },
        ],
      };
    } else {
      body = { ...body, options: options.map((o) => ({ text: o.text.trim(), is_correct: o.is_correct })) };
    }

    const path = questionId
      ? `/institutions/${institutionId}/questions/${questionId}/versions`
      : `/institutions/${institutionId}/questions`;

    try {
      await api(path, { method: "POST", body });
      oncreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save question.");
    } finally {
      setBusy(false);
    }
  }

  const isChoice = type === "single_mcq" || type === "multi_mcq";

  return (
    <Dialog
      open
      onClose={onClose}
      title={questionId ? "New version" : "New question"}
      actions={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={submit} loading={busy} form="question-form" type="submit">
            {questionId ? "Save version" : "Create question"}
          </Button>
        </>
      }
    >
      <form id="question-form" className="stack gap-4" onSubmit={submit}>
        <div className="row gap-3 wrap">
          <Field label="Type">
            <Select value={type} onChange={(e) => changeType(e.target.value as QType)} aria-label="Question type">
              <option value="single_mcq">Single choice</option>
              <option value="multi_mcq">Multi select</option>
              <option value="true_false">True / False</option>
              <option value="numerical">Numerical</option>
            </Select>
          </Field>
          <Field label="Difficulty">
            <Select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} aria-label="Difficulty">
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </Select>
          </Field>
          <Field label="Marks">
            <Input
              type="number"
              min={1}
              value={marks}
              onChange={(e) => setMarks(Math.max(1, Number(e.target.value) || 1))}
              aria-label="Marks"
              style={{ width: 90 }}
            />
          </Field>
        </div>

        <Field label="Question text">
          <Textarea required value={text} onChange={(e) => setText(e.target.value)} placeholder="Enter the question prompt…" aria-label="Question text" />
        </Field>

        {isChoice && (
          <Field label="Options" hint={type === "single_mcq" ? "Mark exactly one correct answer." : "Mark one or more correct answers."}>
            <div className="stack gap-2">
              {options.map((o, i) => (
                <div key={i} className="row gap-2">
                  <input
                    type={type === "single_mcq" ? "radio" : "checkbox"}
                    name="correct-option"
                    checked={o.is_correct}
                    onChange={() => setCorrect(i)}
                    aria-label={`Mark option ${i + 1} correct`}
                  />
                  <Input
                    value={o.text}
                    onChange={(e) => setOptions((prev) => prev.map((p, idx) => (idx === i ? { ...p, text: e.target.value } : p)))}
                    placeholder={`Option ${i + 1}`}
                    aria-label={`Option ${i + 1} text`}
                  />
                  {options.length > 2 && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="btn-icon"
                      aria-label="Remove option"
                      onClick={() => setOptions((prev) => prev.filter((_, idx) => idx !== i))}
                    >
                      <Icon.Close size={16} />
                    </Button>
                  )}
                </div>
              ))}
              <div>
                <Button type="button" variant="ghost" size="sm" icon={<Icon.Plus size={16} />} onClick={() => setOptions((o) => [...o, { text: "", is_correct: false }])}>
                  Add option
                </Button>
              </div>
            </div>
          </Field>
        )}

        {type === "true_false" && (
          <Field label="Correct answer">
            <Select value={tfCorrect} onChange={(e) => setTfCorrect(e.target.value as "True" | "False")} aria-label="Correct answer">
              <option value="True">True</option>
              <option value="False">False</option>
            </Select>
          </Field>
        )}

        {type === "numerical" && (
          <div className="row gap-3 wrap">
            <Field label="Correct value">
              <Input value={numAnswer} onChange={(e) => setNumAnswer(e.target.value)} placeholder="e.g. 42" inputMode="decimal" aria-label="Correct value" required />
            </Field>
            <Field label="Tolerance (±)" hint="Optional absolute tolerance.">
              <Input value={numTolerance} onChange={(e) => setNumTolerance(e.target.value)} placeholder="e.g. 0.5" inputMode="decimal" aria-label="Tolerance" />
            </Field>
          </div>
        )}

        <Field label="Explanation (optional)" hint="Shown to staff only — never exposed to students.">
          <Textarea value={explanation} onChange={(e) => setExplanation(e.target.value)} aria-label="Explanation" />
        </Field>

        {error && <Alert tone="error">{error}</Alert>}
      </form>
    </Dialog>
  );
}
