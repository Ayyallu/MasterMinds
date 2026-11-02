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
  EmptyState,
  Field,
  Input,
  PageHeader,
  Select,
  Table,
  Tabs,
  useAsync,
  useToast,
} from "@/components/ui";

type YearRow = { id: number; name: string; is_current: boolean };
type ClassGroupRow = { id: number; name: string; kind: string };

export default function AcademicPage() {
  const me = useMe();
  const institutionId = me.institution_ids[0];
  const [tab, setTab] = useState<"years" | "structure" | "groups">("years");

  if (!institutionId) {
    return (
      <>
        <PageHeader title="Academic structure" />
        <Card>
          <p className="muted">No institution is linked to your account.</p>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Academic structure"
        subtitle="Define the academic framework: years, terms, grades, departments, courses and class groups."
      />
      <Tabs
        tabs={[
          { id: "years", label: "Years & terms" },
          { id: "structure", label: "Grades, departments & courses" },
          { id: "groups", label: "Class groups" },
        ]}
        value={tab}
        onChange={setTab}
      />
      {tab === "years" && <YearsTab institutionId={institutionId} />}
      {tab === "structure" && <StructureTab institutionId={institutionId} />}
      {tab === "groups" && <GroupsTab institutionId={institutionId} />}
    </>
  );
}

function YearsTab({ institutionId }: { institutionId: number }) {
  const toast = useToast();
  const years = useAsync<YearRow[]>(() => api(`/institutions/${institutionId}/academic-years`), [institutionId]);
  const [name, setName] = useState("");
  const [isCurrent, setIsCurrent] = useState(false);
  const [busy, setBusy] = useState(false);

  const [termName, setTermName] = useState("");
  const [termYear, setTermYear] = useState("");
  const [termSeq, setTermSeq] = useState(1);
  const [termBusy, setTermBusy] = useState(false);

  async function addYear(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api(`/institutions/${institutionId}/academic-years`, { method: "POST", body: { name: name.trim(), is_current: isCurrent } });
      setName("");
      setIsCurrent(false);
      toast.push("Academic year created.", "success");
      await years.reload();
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Could not create year.", "error");
    } finally {
      setBusy(false);
    }
  }

  async function addTerm(e: React.FormEvent) {
    e.preventDefault();
    setTermBusy(true);
    try {
      await api(`/institutions/${institutionId}/terms`, {
        method: "POST",
        body: { academic_year_id: Number(termYear), name: termName.trim(), sequence: termSeq },
      });
      setTermName("");
      toast.push("Term created.", "success");
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Could not create term.", "error");
    } finally {
      setTermBusy(false);
    }
  }

  return (
    <div className="grid grid-cards" style={{ alignItems: "start" }}>
      <Card pad={false}>
        <CardHeader title="Academic years" />
        <AsyncView
          state={years}
          isEmpty={(d) => d.length === 0}
          empty={<EmptyState icon={<Icon.Calendar size={24} />} title="No academic years yet">Create your first academic year to begin.</EmptyState>}
        >
          {(rows) => (
            <Table columns={["Name", "Current"]}>
              {rows.map((y) => (
                <tr key={y.id}>
                  <td className="strong">{y.name}</td>
                  <td>{y.is_current ? <Badge tone="success" dot>Current</Badge> : <span className="faint">—</span>}</td>
                </tr>
              ))}
            </Table>
          )}
        </AsyncView>
      </Card>

      <div className="stack gap-4">
        <Card pad={false}>
          <CardHeader title="New academic year" />
          <form className="card-pad stack gap-4" onSubmit={addYear}>
            <Field label="Name">
              <Input required value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. 2025–2026" aria-label="Academic year name" />
            </Field>
            <label className="row gap-2 text-sm">
              <input type="checkbox" checked={isCurrent} onChange={(e) => setIsCurrent(e.target.checked)} /> Mark as current year
            </label>
            <div>
              <Button type="submit" loading={busy} icon={<Icon.Plus size={16} />}>Add year</Button>
            </div>
          </form>
        </Card>

        <Card pad={false}>
          <CardHeader title="New term" />
          <form className="card-pad stack gap-4" onSubmit={addTerm}>
            <Field label="Academic year">
              <Select required value={termYear} onChange={(e) => setTermYear(e.target.value)} aria-label="Academic year">
                <option value="">Select a year…</option>
                {years.data?.map((y) => (
                  <option key={y.id} value={y.id}>
                    {y.name}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="row gap-3 wrap">
              <Field label="Term name">
                <Input required value={termName} onChange={(e) => setTermName(e.target.value)} placeholder="e.g. Semester 1" aria-label="Term name" />
              </Field>
              <Field label="Sequence">
                <Input type="number" min={1} value={termSeq} onChange={(e) => setTermSeq(Math.max(1, Number(e.target.value) || 1))} aria-label="Sequence" style={{ width: 90 }} />
              </Field>
            </div>
            <div>
              <Button type="submit" loading={termBusy} disabled={!termYear} icon={<Icon.Plus size={16} />}>Add term</Button>
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
}

function SimpleCreateCard({
  title,
  institutionId,
  path,
  fields,
}: {
  title: string;
  institutionId: number;
  path: string;
  fields: { key: string; label: string; required?: boolean; placeholder?: string }[];
}) {
  const toast = useToast();
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const body: Record<string, unknown> = {};
      for (const f of fields) {
        const v = (values[f.key] ?? "").trim();
        body[f.key] = v || null;
      }
      await api(`/institutions/${institutionId}${path}`, { method: "POST", body });
      setValues({});
      toast.push(`${title} created.`, "success");
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Could not create.", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card pad={false}>
      <CardHeader title={title} />
      <form className="card-pad stack gap-4" onSubmit={submit}>
        {fields.map((f) => (
          <Field key={f.key} label={f.label}>
            <Input
              required={f.required}
              value={values[f.key] ?? ""}
              onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
              placeholder={f.placeholder}
              aria-label={f.label}
            />
          </Field>
        ))}
        <div>
          <Button type="submit" loading={busy} icon={<Icon.Plus size={16} />}>Create</Button>
        </div>
      </form>
    </Card>
  );
}

function StructureTab({ institutionId }: { institutionId: number }) {
  return (
    <div className="grid grid-cards" style={{ alignItems: "start" }}>
      <SimpleCreateCard
        title="Grade level"
        institutionId={institutionId}
        path="/grade-levels"
        fields={[{ key: "name", label: "Name", required: true, placeholder: "e.g. Grade 10" }]}
      />
      <SimpleCreateCard
        title="Department"
        institutionId={institutionId}
        path="/departments"
        fields={[
          { key: "name", label: "Name", required: true, placeholder: "e.g. Science" },
          { key: "code", label: "Code (optional)", placeholder: "e.g. SCI" },
        ]}
      />
      <SimpleCreateCard
        title="Course"
        institutionId={institutionId}
        path="/courses"
        fields={[
          { key: "name", label: "Name", required: true, placeholder: "e.g. Physics" },
          { key: "code", label: "Code", required: true, placeholder: "e.g. PHY101" },
        ]}
      />
    </div>
  );
}

function GroupsTab({ institutionId }: { institutionId: number }) {
  const toast = useToast();
  const groups = useAsync<ClassGroupRow[]>(() => api(`/institutions/${institutionId}/class-groups`), [institutionId]);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("class");
  const [busy, setBusy] = useState(false);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api(`/institutions/${institutionId}/class-groups`, { method: "POST", body: { name: name.trim(), kind } });
      setName("");
      toast.push("Class group created.", "success");
      await groups.reload();
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Could not create group.", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid grid-cards" style={{ alignItems: "start" }}>
      <Card pad={false}>
        <CardHeader title="Class groups" />
        <AsyncView
          state={groups}
          isEmpty={(d) => d.length === 0}
          empty={<EmptyState icon={<Icon.Users size={24} />} title="No class groups yet">Create classes, sections or batches here.</EmptyState>}
        >
          {(rows) => (
            <Table columns={["Name", "Kind"]}>
              {rows.map((g) => (
                <tr key={g.id}>
                  <td className="strong">{g.name}</td>
                  <td>
                    <Badge tone="neutral">{g.kind}</Badge>
                  </td>
                </tr>
              ))}
            </Table>
          )}
        </AsyncView>
      </Card>
      <Card pad={false}>
        <CardHeader title="New class group" />
        <form className="card-pad stack gap-4" onSubmit={add}>
          <Field label="Name">
            <Input required value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Grade 10 - Section A" aria-label="Class group name" />
          </Field>
          <Field label="Kind">
            <Select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Kind">
              <option value="class">Class</option>
              <option value="section">Section</option>
              <option value="batch">Batch</option>
            </Select>
          </Field>
          <Alert tone="info">
            Grade, term and course links can be set via roster import and enrollment workflows.
          </Alert>
          <div>
            <Button type="submit" loading={busy} icon={<Icon.Plus size={16} />}>Add group</Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
