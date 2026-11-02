"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Icon } from "@/components/icons";
import { ReportView, type ExamReport } from "@/components/ReportView";
import { Alert, Button, Card, Field, Input, PageHeader, Spinner } from "@/components/ui";

export default function PlatformReportsPage() {
  const [institutionId, setInstitutionId] = useState("");
  const [examId, setExamId] = useState("");
  const [report, setReport] = useState<ExamReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setReport(null);
    try {
      const res = await api<ExamReport>(
        `/admin/institutions/${Number(institutionId)}/exams/${Number(examId)}/report`,
      );
      setReport(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load report.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Platform reports"
        subtitle="Audited cross-tenant exam reporting. Every access is recorded in the audit log."
      />

      <Card style={{ maxWidth: 620, marginBottom: "var(--s-6)" }}>
        <form className="stack gap-4" onSubmit={run}>
          <div className="row gap-3 wrap">
            <Field label="Institution ID">
              <Input
                inputMode="numeric"
                value={institutionId}
                onChange={(e) => setInstitutionId(e.target.value.replace(/[^0-9]/g, ""))}
                placeholder="12"
                aria-label="Institution ID"
                required
              />
            </Field>
            <Field label="Exam ID">
              <Input
                inputMode="numeric"
                value={examId}
                onChange={(e) => setExamId(e.target.value.replace(/[^0-9]/g, ""))}
                placeholder="340"
                aria-label="Exam ID"
                required
              />
            </Field>
          </div>
          <Alert tone="warning">
            Cross-tenant access is audited. Only query data you are authorized to review.
          </Alert>
          {error && <Alert tone="error">{error}</Alert>}
          <div>
            <Button type="submit" icon={<Icon.Search size={16} />} loading={busy} disabled={!institutionId || !examId}>
              Load report
            </Button>
          </div>
        </form>
      </Card>

      {busy && (
        <div className="row gap-3 muted">
          <Spinner /> Loading report…
        </div>
      )}
      {report && <ReportView report={report} />}
    </>
  );
}
