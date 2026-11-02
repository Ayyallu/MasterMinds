"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useMe } from "@/components/SessionProvider";
import { Icon } from "@/components/icons";
import {
  Alert,
  AsyncView,
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  Input,
  Select,
  Stat,
  Table,
  Tabs,
  Textarea,
  useAsync,
  useToast,
} from "@/components/ui";

type ClassGroupRow = { id: number; name: string; kind: string };
type RosterResult = {
  import_id: number;
  status: string;
  total_rows: number;
  valid_rows: number;
  error_rows: number;
  errors: { row: number; message: string }[];
  committed: boolean;
};

export default function PeoplePage() {
  const me = useMe();
  const institutionId = me.institution_ids[0];
  const [tab, setTab] = useState<"invite" | "approve" | "enroll" | "roster">("invite");

  if (!institutionId) {
    return (
      <>
        <PageHeaderLocal />
        <Card>
          <p className="muted">No institution is linked to your account.</p>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeaderLocal />
      <Tabs
        tabs={[
          { id: "invite", label: "Invitations" },
          { id: "approve", label: "Approvals" },
          { id: "enroll", label: "Enrollment" },
          { id: "roster", label: "Roster import" },
        ]}
        value={tab}
        onChange={setTab}
      />
      {tab === "invite" && <InviteTab institutionId={institutionId} />}
      {tab === "approve" && <ApproveTab institutionId={institutionId} />}
      {tab === "enroll" && <EnrollTab institutionId={institutionId} />}
      {tab === "roster" && <RosterTab institutionId={institutionId} />}
    </>
  );
}

function PageHeaderLocal() {
  return (
    <div className="page-header">
      <div>
        <h1 className="page-title">People</h1>
        <p className="page-subtitle">Invite staff, approve students, enroll learners and import rosters.</p>
      </div>
    </div>
  );
}

function InviteTab({ institutionId }: { institutionId: number }) {
  const toast = useToast();
  const [role, setRole] = useState("teacher");
  const [email, setEmail] = useState("");
  const [registerNumber, setRegisterNumber] = useState("");
  const [busy, setBusy] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setToken(null);
    try {
      const res = await api<{ debug_invitation_token?: string }>(`/institutions/${institutionId}/invitations`, {
        method: "POST",
        body: {
          role,
          email: email.trim() || null,
          register_number: registerNumber.trim() || null,
        },
      });
      toast.push("Invitation created.", "success");
      if (res.debug_invitation_token) setToken(res.debug_invitation_token);
      setEmail("");
      setRegisterNumber("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create invitation.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid grid-cards" style={{ alignItems: "start" }}>
      <Card pad={false}>
        <CardHeader title="Invite a member" />
        <form className="card-pad stack gap-4" onSubmit={submit}>
          <Field label="Role">
            <Select value={role} onChange={(e) => setRole(e.target.value)} aria-label="Role">
              <option value="teacher">Teacher / Faculty</option>
              <option value="institution_admin">Institution Admin</option>
              <option value="student">Student</option>
            </Select>
          </Field>
          <Field label="Email (optional)">
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="member@institution.edu" aria-label="Email" />
          </Field>
          <Field label="Register number (optional)" hint="For student invitations.">
            <Input value={registerNumber} onChange={(e) => setRegisterNumber(e.target.value)} aria-label="Register number" />
          </Field>
          {token && (
            <Field label="Invitation token" hint="Share securely — shown only in non-production.">
              <Input readOnly value={token} className="mono text-xs" onFocus={(e) => e.currentTarget.select()} />
            </Field>
          )}
          {error && <Alert tone="error">{error}</Alert>}
          <div>
            <Button type="submit" loading={busy} icon={<Icon.Plus size={16} />}>Create invitation</Button>
          </div>
        </form>
      </Card>
      <Card>
        <div className="row gap-3 items-start">
          <Icon.Info size={18} />
          <p className="muted text-sm" style={{ margin: 0 }}>
            Invited staff accept via an invitation token to set their name and password. Invited
            students can also self-register and then be approved under the Approvals tab.
          </p>
        </div>
      </Card>
    </div>
  );
}

function ApproveTab({ institutionId }: { institutionId: number }) {
  const toast = useToast();
  const [userId, setUserId] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ user_id: number; status: string }>(`/institutions/${institutionId}/memberships/approve`, {
        method: "POST",
        body: { user_id: Number(userId) },
      });
      setResult(`User #${res.user_id} is now ${res.status}.`);
      setUserId("");
      toast.push("Membership approved.", "success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not approve membership.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card style={{ maxWidth: 520 }}>
      <CardHeader title="Approve a pending membership" />
      <form className="card-pad stack gap-4" onSubmit={submit}>
        <p className="muted text-sm">
          Students who self-register remain pending until approved. Enter the user ID to approve
          their membership.
        </p>
        <Field label="User ID">
          <Input inputMode="numeric" value={userId} onChange={(e) => setUserId(e.target.value.replace(/[^0-9]/g, ""))} placeholder="e.g. 204" aria-label="User ID" required />
        </Field>
        {result && <Alert tone="success">{result}</Alert>}
        {error && <Alert tone="error">{error}</Alert>}
        <div>
          <Button type="submit" loading={busy} disabled={!userId} icon={<Icon.Check size={16} />}>Approve membership</Button>
        </div>
      </form>
    </Card>
  );
}

function EnrollTab({ institutionId }: { institutionId: number }) {
  const toast = useToast();
  const groups = useAsync<ClassGroupRow[]>(() => api(`/institutions/${institutionId}/class-groups`), [institutionId]);
  const [studentId, setStudentId] = useState("");
  const [classGroupId, setClassGroupId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function enroll(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api(`/institutions/${institutionId}/enrollments`, {
        method: "POST",
        body: { student_user_id: Number(studentId), class_group_id: Number(classGroupId) },
      });
      setStudentId("");
      toast.push("Student enrolled.", "success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not enroll student.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card style={{ maxWidth: 520 }}>
      <CardHeader title="Enroll a student" />
      <form className="card-pad stack gap-4" onSubmit={enroll}>
        <Field label="Student user ID">
          <Input inputMode="numeric" value={studentId} onChange={(e) => setStudentId(e.target.value.replace(/[^0-9]/g, ""))} placeholder="e.g. 204" aria-label="Student user ID" required />
        </Field>
        <Field label="Class group">
          <AsyncView state={groups}>
            {(rows) => (
              <Select value={classGroupId} onChange={(e) => setClassGroupId(e.target.value)} aria-label="Class group" required>
                <option value="">Select a class group…</option>
                {rows.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </Select>
            )}
          </AsyncView>
        </Field>
        <Alert tone="info">Transfers preserve history: enrolling into a new group closes the previous enrollment row.</Alert>
        {error && <Alert tone="error">{error}</Alert>}
        <div>
          <Button type="submit" loading={busy} disabled={!studentId || !classGroupId} icon={<Icon.Plus size={16} />}>Enroll student</Button>
        </div>
      </form>
    </Card>
  );
}

function RosterTab({ institutionId }: { institutionId: number }) {
  const toast = useToast();
  const [csv, setCsv] = useState("");
  const [classCode, setClassCode] = useState("");
  const [preview, setPreview] = useState<RosterResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(commit: boolean) {
    setBusy(true);
    setError(null);
    try {
      const res = await api<RosterResult>(`/institutions/${institutionId}/roster/import`, {
        method: "POST",
        body: { csv_text: csv, class_group_code: classCode.trim() || null, commit },
      });
      setPreview(res);
      if (commit) toast.push(`Imported ${res.valid_rows} rows.`, "success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Roster import failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack gap-6">
      <Card pad={false}>
        <CardHeader title="Import roster from CSV" />
        <div className="card-pad stack gap-4">
          <Field label="Class group code (optional)">
            <Input value={classCode} onChange={(e) => setClassCode(e.target.value)} placeholder="e.g. G10-A" aria-label="Class group code" style={{ maxWidth: 260 }} />
          </Field>
          <Field label="CSV content" hint="Paste roster rows. Validate first, then commit once clean.">
            <Textarea
              value={csv}
              onChange={(e) => setCsv(e.target.value)}
              style={{ minHeight: 160, fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)" }}
              placeholder={"register_number,full_name,email\n2025-001,Jane Doe,jane@example.com"}
              aria-label="CSV content"
            />
          </Field>
          {error && <Alert tone="error">{error}</Alert>}
          <div className="row gap-3 wrap">
            <Button variant="secondary" onClick={() => run(false)} loading={busy} disabled={!csv.trim()} icon={<Icon.Search size={16} />}>
              Validate (preview)
            </Button>
            <Button
              onClick={() => run(true)}
              loading={busy}
              disabled={!csv.trim() || !preview || preview.error_rows > 0}
              icon={<Icon.Upload size={16} />}
            >
              Commit import
            </Button>
          </div>
          {preview && preview.error_rows > 0 && (
            <Alert tone="warning">Resolve the {preview.error_rows} error row(s) below before committing.</Alert>
          )}
        </div>
      </Card>

      {preview && (
        <Card pad={false}>
          <CardHeader
            title={`Import #${preview.import_id}`}
            action={<Badge tone={preview.committed ? "success" : "warning"} dot>{preview.committed ? "Committed" : "Preview"}</Badge>}
          />
          <div className="card-pad stack gap-4">
            <div className="grid grid-stats">
              <Stat label="Total rows" value={preview.total_rows} icon={<Icon.FileText size={18} />} />
              <Stat label="Valid" value={preview.valid_rows} icon={<Icon.CheckCircle size={18} />} />
              <Stat label="Errors" value={preview.error_rows} icon={<Icon.AlertCircle size={18} />} />
            </div>
            {preview.errors.length > 0 && (
              <Table columns={["Row", "Error"]}>
                {preview.errors.map((er, i) => (
                  <tr key={i}>
                    <td className="mono">#{er.row}</td>
                    <td style={{ color: "var(--danger-700)" }}>{er.message}</td>
                  </tr>
                ))}
              </Table>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
