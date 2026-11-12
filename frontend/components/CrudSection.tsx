"use client";

/* Reusable "list with edit/delete + create form" block for simple admin
   resources that expose GET/POST/PUT/DELETE under one path. */

import { useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { Icon } from "@/components/icons";
import {
  AsyncView,
  Button,
  Card,
  CardHeader,
  ConfirmDialog,
  Dialog,
  EmptyState,
  Field,
  Input,
  Select,
  Table,
  useAsync,
  useToast,
} from "@/components/ui";

export type CrudField = {
  key: string;
  label: string;
  type?: "text" | "number" | "select" | "checkbox";
  required?: boolean;
  placeholder?: string;
  /** For select fields. A "None" choice is added unless required. */
  options?: { value: number | string; label: string }[];
  /** Select values are numeric ids (default). Set false for string enums. */
  numeric?: boolean;
  default?: string | number | boolean;
};

export type CrudRow = { id: number } & Record<string, unknown>;

export type CrudColumn = {
  label: string;
  render: (row: CrudRow) => ReactNode;
};

type Values = Record<string, string | boolean>;

function initialValues(fields: CrudField[], row?: CrudRow): Values {
  const out: Values = {};
  for (const f of fields) {
    const raw = row ? row[f.key] : f.default;
    if (f.type === "checkbox") out[f.key] = Boolean(raw);
    else out[f.key] = raw === null || raw === undefined ? "" : String(raw);
  }
  return out;
}

function buildBody(fields: CrudField[], values: Values, base?: CrudRow) {
  // Start from the existing row so fields not shown in the form (e.g. dates)
  // are preserved on a full-replace PUT.
  const body: Record<string, unknown> = base ? { ...base } : {};
  delete body.id;
  for (const f of fields) {
    const v = values[f.key];
    if (f.type === "checkbox") body[f.key] = Boolean(v);
    else if (f.type === "number") body[f.key] = Number(v) || 0;
    else if (f.type === "select" && f.numeric !== false) body[f.key] = v === "" ? null : Number(v);
    else {
      const t = String(v).trim();
      body[f.key] = t === "" && !f.required ? null : t;
    }
  }
  return body;
}

function FormFields({
  fields,
  values,
  setValues,
}: {
  fields: CrudField[];
  values: Values;
  setValues: (fn: (v: Values) => Values) => void;
}) {
  const set = (k: string, v: string | boolean) => setValues((cur) => ({ ...cur, [k]: v }));
  return (
    <>
      {fields.map((f) => {
        if (f.type === "checkbox") {
          return (
            <label key={f.key} className="row gap-2 text-sm">
              <input type="checkbox" checked={Boolean(values[f.key])} onChange={(e) => set(f.key, e.target.checked)} /> {f.label}
            </label>
          );
        }
        return (
          <Field key={f.key} label={f.label}>
            {f.type === "select" ? (
              <Select required={f.required} value={String(values[f.key])} onChange={(e) => set(f.key, e.target.value)} aria-label={f.label}>
                <option value="">{f.required ? "Select…" : "None"}</option>
                {f.options?.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </Select>
            ) : (
              <Input
                type={f.type === "number" ? "number" : "text"}
                required={f.required}
                value={String(values[f.key])}
                onChange={(e) => set(f.key, e.target.value)}
                placeholder={f.placeholder}
                aria-label={f.label}
              />
            )}
          </Field>
        );
      })}
    </>
  );
}

export function CrudSection({
  title,
  noun,
  basePath,
  fields,
  columns,
  emptyIcon,
  emptyHint,
  onChanged,
}: {
  title: string;
  /** Singular lower-case name used in messages, e.g. "academic year". */
  noun: string;
  /** e.g. `/institutions/1/terms` */
  basePath: string;
  fields: CrudField[];
  columns: CrudColumn[];
  emptyIcon: ReactNode;
  emptyHint: string;
  /** Called after any create/update/delete so dependants can refresh. */
  onChanged?: () => void;
}) {
  const toast = useToast();
  const list = useAsync<CrudRow[]>(() => api(basePath), [basePath]);
  const [values, setValues] = useState(() => initialValues(fields));
  const [creating, setCreating] = useState(false);

  const [editing, setEditing] = useState<CrudRow | null>(null);
  const [editValues, setEditValues] = useState(() => initialValues(fields));
  const [saving, setSaving] = useState(false);

  const [deleting, setDeleting] = useState<CrudRow | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const fail = (err: unknown, fallback: string) =>
    toast.push(err instanceof Error ? err.message : fallback, "error");

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      await api(basePath, { method: "POST", body: buildBody(fields, values) });
      setValues(initialValues(fields));
      toast.push(`${title} created.`, "success");
      await list.reload();
      onChanged?.();
    } catch (err) {
      fail(err, `Could not create ${noun}.`);
    } finally {
      setCreating(false);
    }
  }

  function startEdit(row: CrudRow) {
    setEditing(row);
    setEditValues(initialValues(fields, row));
  }

  async function saveEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editing) return;
    setSaving(true);
    try {
      await api(`${basePath}/${editing.id}`, { method: "PUT", body: buildBody(fields, editValues, editing) });
      toast.push(`${title} updated.`, "success");
      setEditing(null);
      await list.reload();
      onChanged?.();
    } catch (err) {
      fail(err, `Could not update ${noun}.`);
    } finally {
      setSaving(false);
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    setDeleteBusy(true);
    try {
      await api(`${basePath}/${deleting.id}`, { method: "DELETE" });
      toast.push(`${title} deleted.`, "success");
      await list.reload();
      onChanged?.();
    } catch (err) {
      fail(err, `Could not delete ${noun}.`);
    } finally {
      setDeleteBusy(false);
      setDeleting(null);
    }
  }

  return (
    <>
      <Card pad={false}>
        <CardHeader title={`${title} list`} />
        <AsyncView
          state={list}
          isEmpty={(d) => d.length === 0}
          empty={
            <EmptyState icon={emptyIcon} title={`No ${noun}s yet`}>
              {emptyHint}
            </EmptyState>
          }
        >
          {(rows) => (
            <Table columns={[...columns.map((c) => c.label), "Actions"]}>
              {rows.map((r) => (
                <tr key={r.id}>
                  {columns.map((c, i) => (
                    <td key={c.label} className={i === 0 ? "strong" : undefined}>
                      {c.render(r)}
                    </td>
                  ))}
                  <td>
                    <div className="row gap-2">
                      <Button size="sm" variant="secondary" icon={<Icon.Pencil size={14} />} onClick={() => startEdit(r)} aria-label={`Edit ${noun} ${String(r.name ?? r.id)}`}>
                        Edit
                      </Button>
                      <Button size="sm" variant="danger" icon={<Icon.Trash size={14} />} onClick={() => setDeleting(r)} aria-label={`Delete ${noun} ${String(r.name ?? r.id)}`}>
                        Delete
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </Table>
          )}
        </AsyncView>
      </Card>

      <Card pad={false}>
        <CardHeader title={`New ${noun}`} />
        <form className="card-pad stack gap-4" onSubmit={create}>
          <FormFields fields={fields} values={values} setValues={setValues} />
          <div>
            <Button type="submit" loading={creating} icon={<Icon.Plus size={16} />}>
              Create
            </Button>
          </div>
        </form>
      </Card>

      <Dialog open={editing !== null} onClose={() => setEditing(null)} title={`Edit ${noun}`}>
        <form className="stack gap-4" onSubmit={saveEdit}>
          <FormFields fields={fields} values={editValues} setValues={setEditValues} />
          <div className="row gap-2" style={{ justifyContent: "flex-end" }}>
            <Button type="button" variant="secondary" onClick={() => setEditing(null)} disabled={saving}>
              Cancel
            </Button>
            <Button type="submit" loading={saving}>
              Save changes
            </Button>
          </div>
        </form>
      </Dialog>

      <ConfirmDialog
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        onConfirm={confirmDelete}
        title={`Delete ${noun}?`}
        message={`This permanently removes the ${noun}. It cannot be deleted if other records still use it.`}
        confirmLabel="Delete"
        tone="danger"
        loading={deleteBusy}
      />
    </>
  );
}
