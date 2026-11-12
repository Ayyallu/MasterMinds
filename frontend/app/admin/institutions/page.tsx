"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { Icon } from "@/components/icons";
import { InstitutionLogo, typeLabel, type InstitutionProfile } from "@/components/Institution";
import {
  AsyncView,
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  Input,
  PageHeader,
  StatusBadge,
  Table,
  useAsync,
  useToast,
} from "@/components/ui";

export default function InstitutionsPage() {
  const toast = useToast();
  const state = useAsync<InstitutionProfile[]>(() => api<InstitutionProfile[]>("/admin/institutions"), []);
  const [query, setQuery] = useState("");
  const [toggling, setToggling] = useState<InstitutionProfile | null>(null);
  const [busy, setBusy] = useState(false);

  async function toggleStatus() {
    if (!toggling) return;
    const action = toggling.status === "active" ? "disable" : "enable";
    setBusy(true);
    try {
      await api(`/admin/institutions/${toggling.id}/${action}`, { method: "POST" });
      toast.push(`${toggling.name} ${action}d.`, "success");
      await state.reload();
    } catch (err) {
      toast.push(err instanceof Error ? err.message : `Could not ${action} institution.`, "error");
    } finally {
      setBusy(false);
      setToggling(null);
    }
  }

  const q = query.trim().toLowerCase();
  const filter = (rows: InstitutionProfile[]) =>
    q
      ? rows.filter((r) => [r.name, r.code, r.city, r.state, r.country].some((v) => v?.toLowerCase().includes(q)))
      : rows;

  return (
    <>
      <PageHeader
        title="Institutions"
        subtitle="Every school and college on the platform — create new institutions, edit their profiles and control access."
        actions={
          <Link href="/admin/institutions/new" className="btn btn-primary">
            <Icon.Plus size={16} /> New institution
          </Link>
        }
      />

      <Card pad={false}>
        <div className="card-header">
          <span className="card-title">All institutions</span>
          <div style={{ width: 280, maxWidth: "100%" }}>
            <Input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search name, code or city…"
              aria-label="Search institutions"
              style={{ height: 38 }}
            />
          </div>
        </div>
        <AsyncView
          state={state}
          isEmpty={(d) => d.length === 0}
          empty={
            <EmptyState
              icon={<Icon.Building size={24} />}
              title="No institutions yet"
              action={
                <Link href="/admin/institutions/new" className="btn btn-primary btn-sm">
                  <Icon.Plus size={14} /> Create the first institution
                </Link>
              }
            >
              Create an institution directly, or approve a registration request.
            </EmptyState>
          }
        >
          {(rows) => {
            const shown = filter(rows);
            if (shown.length === 0) {
              return <EmptyState icon={<Icon.Search size={24} />} title="No matches">Try a different search.</EmptyState>;
            }
            return (
              <Table columns={["Institution", "Type", "Location", "Contact", "Status", "Actions"]}>
                {shown.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <div className="row gap-3">
                        <InstitutionLogo profile={r} size={40} />
                        <div className="stack" style={{ minWidth: 0 }}>
                          <Link href={`/admin/institutions/${r.id}`} className="strong">
                            {r.name}
                          </Link>
                          <span className="muted text-xs mono">{r.code}</span>
                        </div>
                      </div>
                    </td>
                    <td>{r.institution_type ? <Badge tone="accent">{typeLabel(r.institution_type)}</Badge> : <span className="faint">—</span>}</td>
                    <td className="text-sm">
                      {r.city ? `${r.city}${r.state ? `, ${r.state}` : ""}` : <span className="faint">Profile incomplete</span>}
                    </td>
                    <td className="text-sm muted">{r.email ?? <span className="faint">—</span>}</td>
                    <td>
                      <StatusBadge status={r.status} />
                    </td>
                    <td>
                      <div className="row gap-2">
                        <Link href={`/admin/institutions/${r.id}`} className="btn btn-secondary btn-sm">
                          <Icon.Pencil size={14} /> Edit
                        </Link>
                        <Button
                          size="sm"
                          variant={r.status === "active" ? "ghost" : "success"}
                          onClick={() => setToggling(r)}
                          aria-label={`${r.status === "active" ? "Disable" : "Enable"} ${r.name}`}
                        >
                          {r.status === "active" ? "Disable" : "Enable"}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </Table>
            );
          }}
        </AsyncView>
      </Card>

      <ConfirmDialog
        open={toggling !== null}
        onClose={() => setToggling(null)}
        onConfirm={toggleStatus}
        title={toggling?.status === "active" ? "Disable institution?" : "Enable institution?"}
        message={
          toggling?.status === "active"
            ? `${toggling?.name} will be suspended. You can enable it again at any time.`
            : `${toggling?.name} will be reactivated.`
        }
        confirmLabel={toggling?.status === "active" ? "Disable" : "Enable"}
        tone={toggling?.status === "active" ? "danger" : "success"}
        loading={busy}
      />
    </>
  );
}
