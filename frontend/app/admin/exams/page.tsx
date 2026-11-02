"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useMe } from "@/components/SessionProvider";
import { Icon } from "@/components/icons";
import { ExamForm } from "@/components/ExamForm";
import {
  Alert,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Field,
  Input,
  PageHeader,
  StatusBadge,
  Table,
  useToast,
} from "@/components/ui";
import { getRecentExams, rememberExam, type RecentExam } from "@/lib/recentExams";

export default function ExamsPage() {
  const me = useMe();
  const router = useRouter();
  const toast = useToast();
  const institutionId = me.institution_ids[0];
  const [recent, setRecent] = useState<RecentExam[]>([]);
  const [creating, setCreating] = useState(false);
  const [openId, setOpenId] = useState("");
  const [openError, setOpenError] = useState<string | null>(null);
  const [opening, setOpening] = useState(false);

  useEffect(() => {
    if (institutionId) setRecent(getRecentExams(institutionId));
  }, [institutionId]);

  async function openById(e: React.FormEvent) {
    e.preventDefault();
    if (!institutionId) return;
    setOpening(true);
    setOpenError(null);
    try {
      const exam = await api<{ id: number; title: string; status: string }>(`/institutions/${institutionId}/exams/${Number(openId)}`);
      rememberExam(institutionId, exam);
      router.push(`/admin/exams/${exam.id}`);
    } catch (err) {
      setOpenError(err instanceof Error ? err.message : "Could not open that exam.");
    } finally {
      setOpening(false);
    }
  }

  if (!institutionId) {
    return (
      <>
        <PageHeader title="Exams" />
        <Card>
          <p className="muted">No institution is linked to your account.</p>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Exams"
        subtitle="Draft, submit, approve, schedule and manage the full exam lifecycle."
        actions={
          <Button icon={<Icon.Plus size={16} />} onClick={() => setCreating(true)}>
            Create exam
          </Button>
        }
      />

      <Card pad={false} style={{ marginBottom: "var(--s-6)" }}>
        <CardHeader title="Recent exams" action={<span className="muted text-xs">Opened in this browser</span>} />
        {recent.length === 0 ? (
          <EmptyState icon={<Icon.ClipboardCheck size={24} />} title="No exams opened yet">
            Create an exam, or open one by ID below. The platform has no shared exam list, so this
            panel shows only exams you have created or opened on this device.
          </EmptyState>
        ) : (
          <Table columns={["ID", "Title", "Status", ""]}>
            {recent.map((ex) => (
              <tr key={ex.id}>
                <td className="mono">#{ex.id}</td>
                <td className="strong">{ex.title}</td>
                <td>
                  <StatusBadge status={ex.status} />
                </td>
                <td style={{ textAlign: "right" }}>
                  <Link href={`/admin/exams/${ex.id}`} className="btn btn-secondary btn-sm">
                    Open <Icon.ArrowRight size={14} />
                  </Link>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <Card style={{ maxWidth: 480 }}>
        <CardHeader title="Open an exam by ID" />
        <form className="card-pad row gap-3 items-start wrap" onSubmit={openById}>
          <Field label="Exam ID">
            <Input inputMode="numeric" value={openId} onChange={(e) => setOpenId(e.target.value.replace(/[^0-9]/g, ""))} placeholder="e.g. 340" aria-label="Exam ID" />
          </Field>
          <div style={{ alignSelf: "flex-end" }}>
            <Button type="submit" variant="secondary" loading={opening} disabled={!openId}>
              Open
            </Button>
          </div>
          {openError && (
            <div style={{ flexBasis: "100%" }}>
              <Alert tone="error">{openError}</Alert>
            </div>
          )}
        </form>
      </Card>

      {creating && (
        <ExamForm
          institutionId={institutionId}
          onClose={() => setCreating(false)}
          onCreated={(exam) => {
            rememberExam(institutionId, exam);
            setCreating(false);
            toast.push("Exam draft created.", "success");
            router.push(`/admin/exams/${exam.id}`);
          }}
        />
      )}
    </>
  );
}
