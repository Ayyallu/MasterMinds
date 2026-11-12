"use client";

/* Institution profile building blocks: logo, header chip, profile card and
   the Super Admin create/edit form. */

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, apiBlob, apiUpload } from "@/lib/api";
import { Icon } from "@/components/icons";
import { Alert, Badge, Button, Card, Field, Input, Select, StatusBadge, useAsync, useToast } from "@/components/ui";
import { initials } from "@/lib/session";

export type InstitutionProfile = {
  id: number;
  name: string;
  code: string;
  status: string;
  institution_type: string | null;
  affiliation: string | null;
  established_year: number | null;
  head_name: string | null;
  email: string | null;
  phone: string | null;
  website: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state: string | null;
  postal_code: string | null;
  country: string | null;
  time_zone: string;
  has_logo: boolean;
  created_at: string;
  updated_at: string | null;
};

export const INSTITUTION_TYPES = [
  { value: "school", label: "School" },
  { value: "college", label: "College" },
  { value: "university", label: "University" },
  { value: "other", label: "Other" },
];

export function typeLabel(t: string | null): string {
  return INSTITUTION_TYPES.find((x) => x.value === t)?.label ?? "Institution";
}

/** Head-of-institution title that reads naturally for each type. */
function headTitle(t: string | null): string {
  if (t === "school") return "Principal";
  if (t === "university") return "Vice-Chancellor";
  if (t === "college") return "Principal / Dean";
  return "Head of institution";
}

export const LOGO_MAX_BYTES = 1024 * 1024;
const LOGO_TYPES = ["image/png", "image/jpeg", "image/webp"];

export function validateLogo(file: File): string | null {
  if (!LOGO_TYPES.includes(file.type)) return "Logo must be a PNG, JPEG or WebP image.";
  if (file.size > LOGO_MAX_BYTES) return "Logo must be 1 MB or smaller.";
  return null;
}

export function formatAddress(p: InstitutionProfile): string {
  return [p.address_line1, p.address_line2, p.city, [p.state, p.postal_code].filter(Boolean).join(" "), p.country]
    .filter((x) => x && String(x).trim())
    .join(", ");
}

/** Fetch the profile of an institution the caller belongs to. Errors are
    swallowed (returns null) so branding never breaks the surrounding page. */
export function useInstitutionProfile(institutionId: number | undefined) {
  const state = useAsync<InstitutionProfile | null>(
    () => (institutionId ? api<InstitutionProfile>(`/institutions/${institutionId}/profile`).catch(() => null) : Promise.resolve(null)),
    [institutionId],
  );
  return state;
}

/** Object URL for an institution's logo (fetched with the bearer token). */
export function useLogoUrl(institutionId: number | undefined, hasLogo: boolean, version?: string | null) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!institutionId || !hasLogo) {
      setUrl(null);
      return;
    }
    let objectUrl: string | null = null;
    let cancelled = false;
    apiBlob(`/institutions/${institutionId}/logo`)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => setUrl(null));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [institutionId, hasLogo, version]);
  return url;
}

export function InstitutionLogo({
  profile,
  size = 40,
  src,
}: {
  profile: Pick<InstitutionProfile, "id" | "name" | "has_logo" | "updated_at">;
  size?: number;
  /** Optional override (e.g. a local preview before upload). */
  src?: string | null;
}) {
  const fetched = useLogoUrl(src ? undefined : profile.id, profile.has_logo, profile.updated_at);
  const url = src ?? fetched;
  const style = { width: size, height: size, borderRadius: Math.round(size * 0.28) };
  if (url) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={url} alt={`${profile.name} logo`} className="inst-logo" style={style} />;
  }
  return (
    <span className="inst-logo inst-logo-fallback" style={{ ...style, fontSize: Math.max(12, Math.round(size * 0.36)) }} aria-hidden="true">
      {initials(profile.name)}
    </span>
  );
}

/** Compact logo + name block used in the sidebar / top bar. */
export function InstitutionChip({ institutionId, variant = "dark" }: { institutionId: number | undefined; variant?: "dark" | "light" }) {
  const { data } = useInstitutionProfile(institutionId);
  if (!data) return null;
  return (
    <div className={`inst-chip inst-chip-${variant}`} title={data.name}>
      <InstitutionLogo profile={data} size={variant === "dark" ? 36 : 30} />
      <div className="stack" style={{ minWidth: 0 }}>
        <span className="inst-chip-name">{data.name}</span>
        <span className="inst-chip-meta">
          {typeLabel(data.institution_type)} · {data.code}
        </span>
      </div>
    </div>
  );
}

function InfoRow({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="inst-info-row">
      <span className="inst-info-icon">{icon}</span>
      <div className="stack" style={{ minWidth: 0 }}>
        <span className="inst-info-label">{label}</span>
        <span className="inst-info-value">{children}</span>
      </div>
    </div>
  );
}

/** Full profile card shown to members (admin / faculty / student). */
export function InstitutionProfileCard({
  profile,
  canEditLogo,
  onChanged,
}: {
  profile: InstitutionProfile;
  canEditLogo?: boolean;
  onChanged?: () => void;
}) {
  const toast = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const address = formatAddress(profile);
  const missing = !profile.institution_type && !address;

  async function upload(file: File) {
    const problem = validateLogo(file);
    if (problem) {
      toast.push(problem, "error");
      return;
    }
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      await apiUpload(`/institutions/${profile.id}/logo`, form);
      toast.push("Logo updated.", "success");
      onChanged?.();
    } catch (err) {
      toast.push(err instanceof Error ? err.message : "Could not upload logo.", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card pad={false} className="inst-card">
      <div className="inst-hero">
        <InstitutionLogo profile={profile} size={72} />
        <div className="stack gap-1" style={{ minWidth: 0 }}>
          <div className="row gap-2 wrap">
            <Badge tone="accent">{typeLabel(profile.institution_type)}</Badge>
            <Badge tone="neutral">{profile.code}</Badge>
            {profile.status !== "active" && <StatusBadge status={profile.status} />}
          </div>
          <h2 className="inst-name">{profile.name}</h2>
          {(profile.affiliation || profile.established_year) && (
            <span className="muted text-sm">
              {[profile.affiliation, profile.established_year ? `Est. ${profile.established_year}` : null].filter(Boolean).join(" · ")}
            </span>
          )}
        </div>
        {canEditLogo && (
          <div style={{ marginLeft: "auto" }}>
            <input
              ref={fileRef}
              type="file"
              accept={LOGO_TYPES.join(",")}
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                e.target.value = "";
                if (f) void upload(f);
              }}
            />
            <Button size="sm" variant="secondary" loading={busy} icon={<Icon.Upload size={14} />} onClick={() => fileRef.current?.click()}>
              {profile.has_logo ? "Change logo" : "Add logo"}
            </Button>
          </div>
        )}
      </div>
      {missing ? (
        <div className="card-pad">
          <Alert tone="info">The institution profile hasn&apos;t been completed yet. Your Super Admin can add the address and contact details.</Alert>
        </div>
      ) : (
        <div className="inst-info-grid card-pad">
          {profile.head_name && (
            <InfoRow icon={<Icon.User size={16} />} label={headTitle(profile.institution_type)}>
              {profile.head_name}
            </InfoRow>
          )}
          {address && (
            <InfoRow icon={<Icon.Building size={16} />} label="Address">
              {address}
            </InfoRow>
          )}
          {profile.email && (
            <InfoRow icon={<Icon.Inbox size={16} />} label="Email">
              <a href={`mailto:${profile.email}`}>{profile.email}</a>
            </InfoRow>
          )}
          {profile.phone && (
            <InfoRow icon={<Icon.Info size={16} />} label="Phone">
              <a href={`tel:${profile.phone.replace(/[^0-9+]/g, "")}`}>{profile.phone}</a>
            </InfoRow>
          )}
          {profile.website && (
            <InfoRow icon={<Icon.Globe size={16} />} label="Website">
              <a href={profile.website} target="_blank" rel="noopener noreferrer">
                {profile.website.replace(/^https?:\/\//, "")}
              </a>
            </InfoRow>
          )}
          <InfoRow icon={<Icon.Clock size={16} />} label="Time zone">
            {profile.time_zone}
          </InfoRow>
        </div>
      )}
    </Card>
  );
}

/* ----------------------------------------------------------------- Form */
export type InstitutionFormValues = {
  name: string;
  code: string;
  institution_type: string;
  affiliation: string;
  established_year: string;
  head_name: string;
  email: string;
  phone: string;
  website: string;
  address_line1: string;
  address_line2: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  time_zone: string;
  admin_full_name: string;
  admin_email: string;
  admin_password: string;
};

export function emptyInstitutionForm(): InstitutionFormValues {
  let tz = "UTC";
  try {
    tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    /* keep UTC */
  }
  return {
    name: "", code: "", institution_type: "", affiliation: "", established_year: "", head_name: "",
    email: "", phone: "", website: "", address_line1: "", address_line2: "", city: "", state: "",
    postal_code: "", country: "", time_zone: tz, admin_full_name: "", admin_email: "", admin_password: "",
  };
}

export function formFromProfile(p: InstitutionProfile): InstitutionFormValues {
  const s = (v: string | number | null) => (v === null || v === undefined ? "" : String(v));
  return {
    ...emptyInstitutionForm(),
    name: p.name, code: p.code, institution_type: s(p.institution_type), affiliation: s(p.affiliation),
    established_year: s(p.established_year), head_name: s(p.head_name), email: s(p.email), phone: s(p.phone),
    website: s(p.website), address_line1: s(p.address_line1), address_line2: s(p.address_line2), city: s(p.city),
    state: s(p.state), postal_code: s(p.postal_code), country: s(p.country), time_zone: p.time_zone || "UTC",
  };
}

/** Build the JSON body for create (includes code + admin) or edit. */
export function institutionBody(v: InstitutionFormValues, mode: "create" | "edit") {
  const body: Record<string, unknown> = {
    name: v.name.trim(),
    institution_type: v.institution_type,
    affiliation: v.affiliation.trim() || null,
    established_year: v.established_year ? Number(v.established_year) : null,
    head_name: v.head_name.trim() || null,
    email: v.email.trim(),
    phone: v.phone.trim(),
    website: v.website.trim() || null,
    address_line1: v.address_line1.trim(),
    address_line2: v.address_line2.trim() || null,
    city: v.city.trim(),
    state: v.state.trim(),
    postal_code: v.postal_code.trim(),
    country: v.country.trim(),
    time_zone: v.time_zone,
  };
  if (mode === "create") {
    body.code = v.code.trim().toUpperCase();
    body.admin_full_name = v.admin_full_name.trim();
    body.admin_email = v.admin_email.trim();
    body.admin_password = v.admin_password || null;
  }
  return body;
}

function timeZones(current: string): string[] {
  let zones: string[] = [];
  try {
    const intl = Intl as unknown as { supportedValuesOf?: (k: string) => string[] };
    zones = intl.supportedValuesOf?.("timeZone") ?? [];
  } catch {
    zones = [];
  }
  if (zones.length === 0) zones = ["UTC", "Asia/Kolkata", "Asia/Dubai", "Asia/Singapore", "Europe/London", "America/New_York"];
  if (!zones.includes("UTC")) zones = ["UTC", ...zones];
  if (current && !zones.includes(current)) zones = [current, ...zones];
  return zones;
}

export function InstitutionForm({
  mode,
  values,
  onChange,
  logoPreview,
  onLogoPick,
  onLogoClear,
  existing,
}: {
  mode: "create" | "edit";
  values: InstitutionFormValues;
  onChange: (v: InstitutionFormValues) => void;
  logoPreview: string | null;
  onLogoPick: (f: File) => void;
  onLogoClear?: () => void;
  existing?: InstitutionProfile;
}) {
  const set = (k: keyof InstitutionFormValues) => (e: { target: { value: string } }) => onChange({ ...values, [k]: e.target.value });
  const zones = useMemo(() => timeZones(values.time_zone), [values.time_zone]);
  const fileRef = useRef<HTMLInputElement>(null);
  const year = new Date().getFullYear();
  const previewProfile = { id: existing?.id ?? 0, name: values.name || "New institution", has_logo: existing?.has_logo ?? false, updated_at: existing?.updated_at ?? null };

  return (
    <div className="stack gap-6">
      <section className="form-section">
        <div className="form-section-head">
          <h3>Basic details</h3>
          <p className="muted text-sm">How the school or college appears to its staff and students.</p>
        </div>
        <div className="form-grid">
          <div className="span-2 logo-picker">
            <InstitutionLogo profile={previewProfile} size={72} src={logoPreview} />
            <div className="stack gap-2">
              <span className="label">Logo</span>
              <span className="hint">PNG, JPEG or WebP, up to 1 MB. A square image works best.</span>
              <div className="row gap-2">
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  hidden
                  aria-label="Logo file"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    e.target.value = "";
                    if (f) onLogoPick(f);
                  }}
                />
                <Button type="button" size="sm" variant="secondary" icon={<Icon.Upload size={14} />} onClick={() => fileRef.current?.click()}>
                  {logoPreview || existing?.has_logo ? "Replace logo" : "Upload logo"}
                </Button>
                {onLogoClear && (logoPreview || existing?.has_logo) && (
                  <Button type="button" size="sm" variant="ghost" onClick={onLogoClear}>
                    Remove
                  </Button>
                )}
              </div>
            </div>
          </div>
          <div className="span-2">
            <Field label="Institution name *">
              <Input required minLength={2} maxLength={255} value={values.name} onChange={set("name")} placeholder="e.g. Sunrise Public School" aria-label="Institution name" />
            </Field>
          </div>
          {mode === "create" ? (
            <Field label="Institution code *" hint="Students use this code to sign in. Letters, digits, - or _.">
              <Input
                required
                minLength={2}
                maxLength={64}
                pattern="[A-Za-z0-9][A-Za-z0-9_\-]{1,63}"
                value={values.code}
                onChange={(e) => onChange({ ...values, code: e.target.value.toUpperCase() })}
                placeholder="e.g. SUNRISE"
                aria-label="Institution code"
              />
            </Field>
          ) : (
            <Field label="Institution code" hint="The sign-in code can't be changed.">
              <Input value={values.code} disabled aria-label="Institution code" />
            </Field>
          )}
          <Field label="Type *">
            <Select required value={values.institution_type} onChange={set("institution_type")} aria-label="Institution type">
              <option value="">Select…</option>
              {INSTITUTION_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Board / affiliation" hint="e.g. CBSE, State Board, Anna University">
            <Input maxLength={255} value={values.affiliation} onChange={set("affiliation")} aria-label="Affiliation" />
          </Field>
          <Field label="Established year">
            <Input type="number" min={1000} max={year} value={values.established_year} onChange={set("established_year")} placeholder={`e.g. ${year - 25}`} aria-label="Established year" />
          </Field>
          <div className="span-2">
            <Field label={`${headTitle(values.institution_type || null)} name`}>
              <Input maxLength={255} value={values.head_name} onChange={set("head_name")} aria-label="Head of institution" />
            </Field>
          </div>
        </div>
      </section>

      <section className="form-section">
        <div className="form-section-head">
          <h3>Contact</h3>
          <p className="muted text-sm">Official contact details shown to members.</p>
        </div>
        <div className="form-grid">
          <Field label="Official email *">
            <Input type="email" required maxLength={320} value={values.email} onChange={set("email")} placeholder="office@school.edu" aria-label="Official email" />
          </Field>
          <Field label="Phone *">
            <Input type="tel" required maxLength={32} pattern="[0-9+()\-.\s]{6,32}" value={values.phone} onChange={set("phone")} placeholder="+91 44 1234 5678" aria-label="Phone" />
          </Field>
          <div className="span-2">
            <Field label="Website">
              <Input maxLength={255} value={values.website} onChange={set("website")} placeholder="www.school.edu" aria-label="Website" />
            </Field>
          </div>
        </div>
      </section>

      <section className="form-section">
        <div className="form-section-head">
          <h3>Address</h3>
          <p className="muted text-sm">Campus address and the time zone used for exam schedules.</p>
        </div>
        <div className="form-grid">
          <div className="span-2">
            <Field label="Address line 1 *">
              <Input required maxLength={255} value={values.address_line1} onChange={set("address_line1")} placeholder="Street and number" aria-label="Address line 1" />
            </Field>
          </div>
          <div className="span-2">
            <Field label="Address line 2">
              <Input maxLength={255} value={values.address_line2} onChange={set("address_line2")} placeholder="Area, landmark (optional)" aria-label="Address line 2" />
            </Field>
          </div>
          <Field label="City *">
            <Input required maxLength={128} value={values.city} onChange={set("city")} aria-label="City" />
          </Field>
          <Field label="State / province *">
            <Input required maxLength={128} value={values.state} onChange={set("state")} aria-label="State" />
          </Field>
          <Field label="Postal code *">
            <Input required maxLength={32} value={values.postal_code} onChange={set("postal_code")} aria-label="Postal code" />
          </Field>
          <Field label="Country *">
            <Input required maxLength={128} value={values.country} onChange={set("country")} aria-label="Country" />
          </Field>
          <div className="span-2">
            <Field label="Time zone *">
              <Select required value={values.time_zone} onChange={set("time_zone")} aria-label="Time zone">
                {zones.map((z) => (
                  <option key={z} value={z}>
                    {z.replaceAll("_", " ")}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
        </div>
      </section>

      {mode === "create" && (
        <section className="form-section">
          <div className="form-section-head">
            <h3>Institution admin</h3>
            <p className="muted text-sm">The first administrator account for this institution. They can then invite faculty and students.</p>
          </div>
          <div className="form-grid">
            <Field label="Full name *">
              <Input required maxLength={255} value={values.admin_full_name} onChange={set("admin_full_name")} aria-label="Admin full name" />
            </Field>
            <Field label="Email *">
              <Input type="email" required maxLength={320} value={values.admin_email} onChange={set("admin_email")} aria-label="Admin email" />
            </Field>
            <div className="span-2">
              <Field label="Initial password" hint="Optional, at least 8 characters. Leave blank to generate a temporary password.">
                <Input type="password" minLength={8} autoComplete="new-password" value={values.admin_password} onChange={set("admin_password")} aria-label="Admin initial password" />
              </Field>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
