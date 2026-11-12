"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, apiUpload } from "@/lib/api";
import { useMe } from "@/components/SessionProvider";
import { Icon } from "@/components/icons";
import {
  InstitutionForm,
  InstitutionProfileCard,
  formFromProfile,
  institutionBody,
  validateLogo,
  type InstitutionFormValues,
  type InstitutionProfile,
} from "@/components/Institution";
import { Alert, AsyncView, Button, Card, PageHeader, useAsync, useToast } from "@/components/ui";

export default function InstitutionDetailPage() {
  const me = useMe();
  const params = useParams<{ institutionId: string }>();
  const id = Number(params.institutionId);
  const state = useAsync<InstitutionProfile>(() => api<InstitutionProfile>(`/institutions/${id}/profile`), [id]);
  const [editing, setEditing] = useState(false);

  if (!me.is_super_admin) {
    return <Alert tone="error">Only a Super Admin can manage institutions.</Alert>;
  }

  return (
    <>
      <PageHeader
        title={state.data?.name ?? "Institution"}
        subtitle="Institution profile as shown to its admins, faculty and students."
        actions={
          <>
            <Link href="/admin/institutions" className="btn btn-secondary">
              <Icon.ChevronLeft size={16} /> All institutions
            </Link>
            {!editing && state.data && (
              <Button icon={<Icon.Pencil size={16} />} onClick={() => setEditing(true)}>
                Edit profile
              </Button>
            )}
          </>
        }
      />
      <AsyncView state={state}>
        {(profile) =>
          editing ? (
            <EditForm
              profile={profile}
              onDone={async (saved) => {
                setEditing(false);
                if (saved) await state.reload();
              }}
            />
          ) : (
            <InstitutionProfileCard profile={profile} canEditLogo onChanged={() => void state.reload()} />
          )
        }
      </AsyncView>
    </>
  );
}

function EditForm({ profile, onDone }: { profile: InstitutionProfile; onDone: (saved: boolean) => void | Promise<void> }) {
  const toast = useToast();
  const [values, setValues] = useState<InstitutionFormValues>(() => formFromProfile(profile));
  const [logo, setLogo] = useState<File | null>(null);
  const [removeLogo, setRemoveLogo] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!logo) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(logo);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [logo]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api(`/admin/institutions/${profile.id}`, { method: "PUT", body: institutionBody(values, "edit") });
      if (logo) {
        const form = new FormData();
        form.append("file", logo);
        await apiUpload(`/institutions/${profile.id}/logo`, form);
      } else if (removeLogo && profile.has_logo) {
        await api(`/institutions/${profile.id}/logo`, { method: "DELETE" });
      }
      toast.push("Institution profile saved.", "success");
      await onDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the profile.");
      window.scrollTo({ top: 0, behavior: "smooth" });
    } finally {
      setBusy(false);
    }
  }

  // When the logo is marked for removal, preview the fallback (initials).
  const shownProfile = removeLogo ? { ...profile, has_logo: false } : profile;

  return (
    <form onSubmit={submit}>
      <Card className="stack gap-6">
        {error && <Alert tone="error">{error}</Alert>}
        <InstitutionForm
          mode="edit"
          values={values}
          onChange={setValues}
          logoPreview={preview}
          existing={shownProfile}
          onLogoPick={(f) => {
            const problem = validateLogo(f);
            if (problem) {
              toast.push(problem, "error");
              return;
            }
            setRemoveLogo(false);
            setLogo(f);
          }}
          onLogoClear={() => {
            setLogo(null);
            setRemoveLogo(true);
          }}
        />
        <div className="row gap-3" style={{ justifyContent: "flex-end" }}>
          <Button type="button" variant="ghost" onClick={() => void onDone(false)} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" loading={busy} icon={<Icon.Check size={16} />}>
            Save changes
          </Button>
        </div>
      </Card>
    </form>
  );
}
