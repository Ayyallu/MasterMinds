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
  Dialog,
  EmptyState,
  Field,
  Input,
  PageHeader,
  StatusBadge,
  Table,
  Tabs,
  useAsync,
  useToast,
} from "@/components/ui";

type Registration = {
  id: number;
  institution_name: string;
  requested_code: string;
  contact_name: string;
  contact_email: string;
  status: string;
};

type Filter = "pending" | "approved" | "rejected";

export default function RegistrationsPage() {
  const toast = useToast();
  const [filter, setFilter] = useState<Filter>("pending");
  const [approving, setApproving] = useState<Registration | null>(null);
  const [rejecting, setRejecting] = useState<Registration | null>(null);

  const state = useAsync<Registration[]>(
    () => api<Registration[]>(`/admin/registrations?status_filter=${filter}`),
    [filter],
  );

  return (
    <>
      <PageHeader
        title="Institution registrations"
        subtitle="Review registration requests, provision Institution Admins, or reject with a reason."
      />

      <Tabs
        tabs={[
          { id: "pending", label: "Pending" },
          { id: "approved", label: "Approved" },
          { id: "rejected", label: "Rejected" },
        ]}
        value={filter}
        onChange={setFilter}
      />

      <AsyncView
        state={state}
        isEmpty={(d) => d.length === 0}
        empty={
          <Card>
            <EmptyState title={`No ${filter} registrations`}>
              {filter === "pending"
                ? "New institution registration requests will appear here for review."
                : `There are no ${filter} registrations to show.`}
            </EmptyState>
          </Card>
        }
      >
        {(rows) => (
          <Table columns={["Institution", "Code", "Contact", "Status", ""]}>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>
                  <strong className="strong">{r.institution_name}</strong>
                </td>
                <td>
                  <Badge tone="neutral">{r.requested_code}</Badge>
                </td>
                <td>
                  <div className="stack">
                    <span>{r.contact_name}</span>
                    <span className="muted text-sm">{r.contact_email}</span>
                  </div>
                </td>
                <td>
                  <StatusBadge status={r.status} />
                </td>
                <td style={{ textAlign: "right" }}>
                  {r.status === "pending" && (
                    <div className="row gap-2" style={{ justifyContent: "flex-end" }}>
                      <Button size="sm" variant="success" icon={<Icon.Check size={16} />} onClick={() => setApproving(r)}>
                        Approve
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => setRejecting(r)}>
                        Reject
                      </Button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </AsyncView>

      {approving && (
        <ApproveDialog
          reg={approving}
          onClose={() => setApproving(null)}
          onDone={() => {
            setApproving(null);
            void state.reload();
          }}
        />
      )}

      <RejectDialog
        reg={rejecting}
        onClose={() => setRejecting(null)}
        onDone={() => {
          toast.push("Registration rejected.", "info");
          setRejecting(null);
          void state.reload();
        }}
      />
    </>
  );
}

function ApproveDialog({
  reg,
  onClose,
  onDone,
}: {
  reg: Registration;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [adminEmail, setAdminEmail] = useState(reg.contact_email);
  const [adminName, setAdminName] = useState(`${reg.institution_name} Admin`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tempPassword, setTempPassword] = useState<string | null>(null);

  async function approve() {
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ debug_admin_temp_password?: string }>(
        `/admin/registrations/${reg.id}/approve`,
        { method: "POST", body: { admin_email: adminEmail.trim(), admin_full_name: adminName.trim() } },
      );
      if (res.debug_admin_temp_password) {
        setTempPassword(res.debug_admin_temp_password);
        toast.push(`${reg.institution_name} approved.`, "success");
      } else {
        toast.push(`${reg.institution_name} approved.`, "success");
        onDone();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open
      onClose={onClose}
      title={`Approve ${reg.institution_name}`}
      actions={
        tempPassword ? (
          <Button onClick={onDone}>Done</Button>
        ) : (
          <>
            <Button variant="secondary" onClick={onClose} disabled={busy}>
              Cancel
            </Button>
            <Button variant="success" onClick={approve} loading={busy}>
              Approve & provision admin
            </Button>
          </>
        )
      }
    >
      {tempPassword ? (
        <div className="stack gap-3">
          <Alert tone="success">Institution approved and the admin account was created.</Alert>
          <Field label="Temporary admin password" hint="Share this securely — it is shown only once.">
            <Input readOnly value={tempPassword} className="mono" onFocus={(e) => e.currentTarget.select()} />
          </Field>
        </div>
      ) : (
        <div className="stack gap-4">
          <p className="muted text-sm">
            Approving creates the institution and provisions its first Institution Admin.
          </p>
          <Field label="Admin email">
            <Input type="email" value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)} aria-label="Admin email" />
          </Field>
          <Field label="Admin full name">
            <Input value={adminName} onChange={(e) => setAdminName(e.target.value)} aria-label="Admin full name" />
          </Field>
          {error && <Alert tone="error">{error}</Alert>}
        </div>
      )}
    </Dialog>
  );
}

function RejectDialog({
  reg,
  onClose,
  onDone,
}: {
  reg: Registration | null;
  onClose: () => void;
  onDone: () => void;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function reject() {
    if (!reg) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/admin/registrations/${reg.id}/reject`, { method: "POST", body: { reason: reason.trim() } });
      setReason("");
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reject failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={!!reg}
      onClose={onClose}
      title={reg ? `Reject ${reg.institution_name}` : ""}
      actions={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button variant="danger" onClick={reject} loading={busy} disabled={!reason.trim()}>
            Reject request
          </Button>
        </>
      }
    >
      <div className="stack gap-4">
        <Field label="Reason" hint="Recorded in the audit log and may be shared with the requester.">
          <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Duplicate institution code" aria-label="Rejection reason" />
        </Field>
        {error && <Alert tone="error">{error}</Alert>}
      </div>
    </Dialog>
  );
}
