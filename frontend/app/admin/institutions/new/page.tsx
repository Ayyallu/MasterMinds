"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, apiUpload } from "@/lib/api";
import { useMe } from "@/components/SessionProvider";
import { Icon } from "@/components/icons";
import {
  InstitutionForm,
  emptyInstitutionForm,
  institutionBody,
  validateLogo,
  type InstitutionProfile,
} from "@/components/Institution";
import { Alert, Button, Card, PageHeader, useToast } from "@/components/ui";

type CreateResult = {
  institution: InstitutionProfile;
  admin_email: string;
  debug_admin_temp_password?: string;
};

export default function NewInstitutionPage() {
  const me = useMe();
  const toast = useToast();
  const [values, setValues] = useState(emptyInstitutionForm);
  const [logo, setLogo] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<CreateResult | null>(null);
  const [logoWarning, setLogoWarning] = useState<string | null>(null);

  useEffect(() => {
    if (!logo) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(logo);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [logo]);

  if (!me.is_super_admin) {
    return (
      <>
        <PageHeader title="New institution" />
        <Alert tone="error">Only a Super Admin can create institutions.</Alert>
      </>
    );
  }

  function pickLogo(f: File) {
    const problem = validateLogo(f);
    if (problem) {
      toast.push(problem, "error");
      return;
    }
    setLogo(f);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setLogoWarning(null);
    try {
      const res = await api<CreateResult>("/admin/institutions", { method: "POST", body: institutionBody(values, "create") });
      if (logo) {
        try {
          const form = new FormData();
          form.append("file", logo);
          await apiUpload(`/institutions/${res.institution.id}/logo`, form);
        } catch (err) {
          setLogoWarning(err instanceof Error ? err.message : "Logo upload failed.");
        }
      }
      setCreated(res);
      toast.push(`${res.institution.name} created.`, "success");
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create institution.");
      window.scrollTo({ top: 0, behavior: "smooth" });
    } finally {
      setBusy(false);
    }
  }

  if (created) {
    const inst = created.institution;
    return (
      <>
        <PageHeader title="Institution created" subtitle={`${inst.name} is active and ready to use.`} />
        <Card className="stack gap-4" style={{ maxWidth: 640 }}>
          <Alert tone="success">
            <strong>{inst.name}</strong> ({inst.code}) has been created and its admin account provisioned.
          </Alert>
          {logoWarning && <Alert tone="warning">The institution was created, but the logo was not saved: {logoWarning}</Alert>}
          <div className="stack gap-2 text-sm">
            <div>
              <span className="muted">Student sign-in code:</span> <span className="mono strong">{inst.code}</span>
            </div>
            <div>
              <span className="muted">Admin sign-in email:</span> <span className="mono">{created.admin_email}</span>
            </div>
            {created.debug_admin_temp_password && (
              <div>
                <span className="muted">Temporary password (development only):</span>{" "}
                <span className="mono strong">{created.debug_admin_temp_password}</span>
              </div>
            )}
          </div>
          <p className="muted text-sm">Share the admin credentials securely. The admin should change the password after first sign-in.</p>
          <div className="row gap-3 wrap">
            <Link href={`/admin/institutions/${inst.id}`} className="btn btn-primary">
              View institution
            </Link>
            <Button
              variant="secondary"
              onClick={() => {
                setCreated(null);
                setValues(emptyInstitutionForm());
                setLogo(null);
              }}
            >
              Create another
            </Button>
            <Link href="/admin/institutions" className="btn btn-ghost">
              Back to list
            </Link>
          </div>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="New institution"
        subtitle="Enter the school or college's basic information. Fields marked * are required."
        actions={
          <Link href="/admin/institutions" className="btn btn-secondary">
            <Icon.ChevronLeft size={16} /> All institutions
          </Link>
        }
      />
      <form onSubmit={submit}>
        <Card className="stack gap-6">
          {error && <Alert tone="error">{error}</Alert>}
          <InstitutionForm
            mode="create"
            values={values}
            onChange={setValues}
            logoPreview={preview}
            onLogoPick={pickLogo}
            onLogoClear={() => setLogo(null)}
          />
          <div className="row gap-3" style={{ justifyContent: "flex-end" }}>
            <Link href="/admin/institutions" className="btn btn-ghost">
              Cancel
            </Link>
            <Button type="submit" loading={busy} icon={<Icon.Check size={16} />}>
              Create institution
            </Button>
          </div>
        </Card>
      </form>
    </>
  );
}
