"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Icon } from "@/components/icons";
import {
  Alert,
  AsyncView,
  Badge,
  Button,
  Card,
  CardHeader,
  ConfirmDialog,
  EmptyState,
  Field,
  Input,
  PageHeader,
  StatusBadge,
  Table,
  useAsync,
  useToast,
} from "@/components/ui";

type Registration = {
  id: number;
  institution_name: string;
  requested_code: string;
  contact_email: string;
  status: string;
};
type Institution = { id: number; name: string; code: string; status: string };

export default function InstitutionsPage() {
  const toast = useToast();
  const state = useAsync<Registration[]>(
    () => api<Registration[]>("/admin/registrations?status_filter=approved"),
    [],
  );

  const [institutionId, setInstitutionId] = useState("");
  const [confirmDisable, setConfirmDisable] = useState(false);
  const [busy, setBusy] = useState(false);
  const [disableError, setDisableError] = useState<string | null>(null);
  const [lastDisabled, setLastDisabled] = useState<Institution | null>(null);

  async function disable() {
    setBusy(true);
    setDisableError(null);
    try {
      const res = await api<Institution>(`/admin/institutions/${Number(institutionId)}/disable`, {
        method: "POST",
      });
      setLastDisabled(res);
      setInstitutionId("");
      setConfirmDisable(false);
      toast.push(`${res.name} disabled.`, "success");
    } catch (err) {
      setDisableError(err instanceof Error ? err.message : "Could not disable institution.");
      setConfirmDisable(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Institutions"
        subtitle="Provisioned institutions across the platform, and administrative controls."
      />

      <Card pad={false} style={{ marginBottom: "var(--s-6)" }}>
        <CardHeader title="Provisioned institutions" />
        <AsyncView
          state={state}
          isEmpty={(d) => d.length === 0}
          empty={
            <EmptyState icon={<Icon.Building size={24} />} title="No approved institutions yet">
              Institutions appear here once their registration has been approved.
            </EmptyState>
          }
        >
          {(rows) => (
            <Table columns={["Institution", "Code", "Admin contact", "Status"]}>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>
                    <strong className="strong">{r.institution_name}</strong>
                  </td>
                  <td>
                    <Badge tone="neutral">{r.requested_code}</Badge>
                  </td>
                  <td className="muted">{r.contact_email}</td>
                  <td>
                    <StatusBadge status="active" />
                  </td>
                </tr>
              ))}
            </Table>
          )}
        </AsyncView>
      </Card>

      <Card style={{ maxWidth: 520 }}>
        <CardHeader title="Disable an institution" />
        <div className="card-pad stack gap-4">
          <p className="muted text-sm">
            Disabling an institution suspends its access. Enter the institution ID (shown when a
            registration is approved).
          </p>
          <Field label="Institution ID">
            <Input
              inputMode="numeric"
              value={institutionId}
              onChange={(e) => setInstitutionId(e.target.value.replace(/[^0-9]/g, ""))}
              placeholder="e.g. 12"
              aria-label="Institution ID"
            />
          </Field>
          {disableError && <Alert tone="error">{disableError}</Alert>}
          {lastDisabled && (
            <Alert tone="success">
              {lastDisabled.name} ({lastDisabled.code}) is now {lastDisabled.status}.
            </Alert>
          )}
          <div>
            <Button
              variant="danger"
              icon={<Icon.Shield size={16} />}
              disabled={!institutionId}
              onClick={() => setConfirmDisable(true)}
            >
              Disable institution
            </Button>
          </div>
        </div>
      </Card>

      <ConfirmDialog
        open={confirmDisable}
        onClose={() => setConfirmDisable(false)}
        onConfirm={disable}
        title="Disable institution?"
        message={`This suspends access for institution #${institutionId}. You can re-enable it later via support tooling.`}
        confirmLabel="Disable"
        tone="danger"
        loading={busy}
      />
    </>
  );
}
