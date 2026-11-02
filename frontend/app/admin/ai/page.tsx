"use client";

import { useState } from "react";
import { useMe } from "@/components/SessionProvider";
import { GenerateForm, JobResult, type Job } from "@/components/AiGenerate";
import { Card, PageHeader } from "@/components/ui";

export default function AiGenerationPage() {
  const me = useMe();
  const institutionId = me.institution_ids[0];
  const [job, setJob] = useState<Job | null>(null);

  if (!institutionId) {
    return (
      <>
        <PageHeader title="AI generation" />
        <Card>
          <p className="muted">No institution is linked to your account.</p>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="AI generation"
        subtitle="Generate reviewed question candidates before an exam. Human approval is always required."
      />
      <div className="grid grid-cards" style={{ alignItems: "start" }}>
        <GenerateForm endpoint={`/institutions/${institutionId}/ai/generate`} onJob={setJob} />
        {job && <JobResult job={job} reviewHref="/admin/questions" />}
      </div>
    </>
  );
}
