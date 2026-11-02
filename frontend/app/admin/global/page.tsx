"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useMe } from "@/components/SessionProvider";
import { Icon } from "@/components/icons";
import { QuestionCard, type QuestionVersion } from "@/components/QuestionView";
import { GenerateForm, JobResult, type Job } from "@/components/AiGenerate";
import {
  Alert,
  Button,
  Card,
  EmptyState,
  Field,
  LoadingState,
  PageHeader,
  Select,
  Spinner,
  Tabs,
  useToast,
} from "@/components/ui";
import { hasRole } from "@/lib/session";

export default function GlobalLibraryPage() {
  const me = useMe();
  const toast = useToast();
  const canReview = hasRole(me, "central_academic_reviewer");
  const [tab, setTab] = useState<"browse" | "generate">("browse");

  const [type, setType] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [status, setStatus] = useState("");
  const [results, setResults] = useState<QuestionVersion[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [actionId, setActionId] = useState<number | null>(null);

  async function search(e?: React.FormEvent) {
    e?.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const body = {
        ...(type ? { type } : {}),
        ...(difficulty ? { difficulty } : {}),
        ...(status ? { status } : {}),
      };
      setResults(await api<QuestionVersion[]>("/global/library/search", { method: "POST", body }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed.");
    } finally {
      setLoading(false);
    }
  }

  async function review(versionId: number, approve: boolean) {
    setActionId(versionId);
    try {
      await api(`/global/questions/versions/${versionId}/review?approve=${approve}`, { method: "POST" });
      toast.push(approve ? "Approved for the global library." : "Rejected.", approve ? "success" : "info");
      await search();
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Review failed.", "error");
    } finally {
      setActionId(null);
    }
  }

  return (
    <>
      <PageHeader
        title="Global library"
        subtitle="Shared questions available to every institution. Only approved global versions are reusable in exams."
      />

      <Tabs
        tabs={[
          { id: "browse", label: "Browse & review" },
          ...(canReview ? [{ id: "generate" as const, label: "Generate" }] : []),
        ]}
        value={tab}
        onChange={setTab}
      />

      {tab === "browse" ? (
        <>
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
              {canReview && (
                <Field label="Status">
                  <Select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">
                    <option value="">Any status</option>
                    <option value="in_review">In review</option>
                    <option value="approved">Approved</option>
                    <option value="rejected">Rejected</option>
                  </Select>
                </Field>
              )}
              <Button type="submit" icon={<Icon.Search size={16} />} loading={loading}>
                Search
              </Button>
            </form>
          </Card>

          {error && <Alert tone="error">{error}</Alert>}

          {loading && results === null ? (
            <LoadingState label="Searching the global library…" />
          ) : results === null ? (
            <Card>
              <EmptyState icon={<Icon.Globe size={24} />} title="Search the global library">
                Use the filters above to browse shared, approved questions.
              </EmptyState>
            </Card>
          ) : results.length === 0 ? (
            <Card>
              <EmptyState icon={<Icon.Search size={24} />} title="No questions match" />
            </Card>
          ) : (
            <div className="stack gap-4">
              {results.map((q) => (
                <div key={q.version_id} className="stack gap-2">
                  <QuestionCard q={q} />
                  {canReview && q.status === "in_review" && (
                    <div className="row gap-2 wrap" style={{ justifyContent: "flex-end" }}>
                      {actionId === q.version_id && <Spinner />}
                      <Button size="sm" variant="success" icon={<Icon.Check size={16} />} disabled={actionId != null} onClick={() => review(q.version_id, true)}>
                        Approve
                      </Button>
                      <Button size="sm" variant="secondary" disabled={actionId != null} onClick={() => review(q.version_id, false)}>
                        Reject
                      </Button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <div className="grid grid-cards" style={{ alignItems: "start" }}>
          <GenerateForm endpoint="/global/ai/generate" global onJob={setJob} />
          {job && <JobResult job={job} reviewHref="#" />}
        </div>
      )}
    </>
  );
}
