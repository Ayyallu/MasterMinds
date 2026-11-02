"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { useMe } from "@/components/SessionProvider";
import { Icon } from "@/components/icons";
import { QuestionCard, type QuestionVersion } from "@/components/QuestionView";
import {
  Alert,
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  LoadingState,
  PageHeader,
  Select,
  Spinner,
  useToast,
} from "@/components/ui";
import { QuestionForm } from "@/components/QuestionForm";

export default function QuestionBankPage() {
  const me = useMe();
  const toast = useToast();
  const institutionId = me.institution_ids[0];
  const isAdmin = me.roles.includes("institution_admin");

  const [type, setType] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [status, setStatus] = useState("");
  const [results, setResults] = useState<QuestionVersion[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [actionId, setActionId] = useState<number | null>(null);

  const search = useCallback(
    async (e?: React.FormEvent) => {
      e?.preventDefault();
      if (!institutionId) return;
      setLoading(true);
      setError(null);
      try {
        const body = {
          ...(type ? { type } : {}),
          ...(difficulty ? { difficulty } : {}),
          ...(status ? { status } : {}),
        };
        setResults(await api<QuestionVersion[]>(`/institutions/${institutionId}/questions/search`, { method: "POST", body }));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Search failed.");
      } finally {
        setLoading(false);
      }
    },
    [institutionId, type, difficulty, status],
  );

  async function submitForReview(versionId: number) {
    setActionId(versionId);
    try {
      await api(`/institutions/${institutionId}/versions/${versionId}/submit`, { method: "POST" });
      toast.push("Submitted for review.", "success");
      await search();
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Could not submit.", "error");
    } finally {
      setActionId(null);
    }
  }

  async function review(versionId: number, approve: boolean) {
    setActionId(versionId);
    try {
      await api(`/institutions/${institutionId}/versions/${versionId}/review?approve=${approve}`, { method: "POST" });
      toast.push(approve ? "Version approved." : "Version rejected.", approve ? "success" : "info");
      await search();
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Review failed.", "error");
    } finally {
      setActionId(null);
    }
  }

  if (!institutionId) {
    return (
      <>
        <PageHeader title="Question bank" />
        <Card>
          <p className="muted">No institution is linked to your account.</p>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Question bank"
        subtitle="Institution-private questions. Editing creates a new immutable version; only approved versions are exam-selectable."
        actions={
          <Button icon={<Icon.Plus size={16} />} onClick={() => setCreating(true)}>
            New question
          </Button>
        }
      />

      <Card style={{ marginBottom: "var(--s-6)" }}>
        <form className="filters" style={{ margin: 0 }} onSubmit={search}>
          <Field label="Type">
            <Select value={type} onChange={(e) => setType(e.target.value)} aria-label="Type">
              <option value="">All types</option>
              <option value="single_mcq">Single choice</option>
              <option value="multi_mcq">Multi select</option>
              <option value="true_false">True / False</option>
              <option value="numerical">Numerical</option>
            </Select>
          </Field>
          <Field label="Difficulty">
            <Select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} aria-label="Difficulty">
              <option value="">Any</option>
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </Select>
          </Field>
          <Field label="Status">
            <Select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">
              <option value="">Any status</option>
              <option value="draft">Draft</option>
              <option value="in_review">In review</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
            </Select>
          </Field>
          <Button type="submit" icon={<Icon.Search size={16} />} loading={loading}>
            Search
          </Button>
        </form>
      </Card>

      {error && <Alert tone="error">{error}</Alert>}

      {loading && results === null ? (
        <LoadingState label="Searching questions…" />
      ) : results === null ? (
        <Card>
          <EmptyState icon={<Icon.FileText size={24} />} title="Search the question bank">
            Use the filters above to find questions, or create your first question.
          </EmptyState>
        </Card>
      ) : results.length === 0 ? (
        <Card>
          <EmptyState icon={<Icon.Search size={24} />} title="No questions match">
            Try widening your filters, or create a new question.
          </EmptyState>
        </Card>
      ) : (
        <div className="stack gap-4">
          {results.map((q) => (
            <div key={q.version_id} className="stack gap-2">
              <QuestionCard q={q} />
              <div className="row gap-2 wrap" style={{ justifyContent: "flex-end" }}>
                {actionId === q.version_id && <Spinner />}
                {q.status === "draft" && (
                  <Button size="sm" variant="secondary" disabled={actionId != null} onClick={() => submitForReview(q.version_id)}>
                    Submit for review
                  </Button>
                )}
                {q.status === "in_review" && isAdmin && (
                  <>
                    <Button size="sm" variant="success" icon={<Icon.Check size={16} />} disabled={actionId != null} onClick={() => review(q.version_id, true)}>
                      Approve
                    </Button>
                    <Button size="sm" variant="secondary" disabled={actionId != null} onClick={() => review(q.version_id, false)}>
                      Reject
                    </Button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {creating && (
        <QuestionForm
          institutionId={institutionId}
          onClose={() => setCreating(false)}
          oncreated={() => {
            setCreating(false);
            toast.push("Question created as draft.", "success");
            void search();
          }}
        />
      )}
    </>
  );
}
