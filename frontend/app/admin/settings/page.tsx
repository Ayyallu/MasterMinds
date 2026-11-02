"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useMe } from "@/components/SessionProvider";
import { Icon } from "@/components/icons";
import {
  Alert,
  Button,
  Card,
  CardHeader,
  Field,
  Input,
  PageHeader,
  useToast,
} from "@/components/ui";

export default function SettingsPage() {
  const me = useMe();
  return (
    <>
      <PageHeader title="Security" subtitle="Manage your password and multi-factor authentication." />
      <div className="grid grid-cards" style={{ alignItems: "start" }}>
        <PasswordCard />
        {me.is_super_admin && <MfaCard />}
      </div>
    </>
  );
}

function PasswordCard() {
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (next !== confirm) {
      setError("New passwords do not match.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api("/auth/password/change", {
        method: "POST",
        body: { current_password: current, new_password: next },
      });
      setCurrent("");
      setNext("");
      setConfirm("");
      toast.push("Password updated.", "success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card pad={false}>
      <CardHeader title="Change password" />
      <form className="card-pad stack gap-4" onSubmit={submit}>
        <Field label="Current password">
          <Input type="password" autoComplete="current-password" required value={current} onChange={(e) => setCurrent(e.target.value)} aria-label="Current password" />
        </Field>
        <Field label="New password" hint="At least 8 characters.">
          <Input type="password" autoComplete="new-password" minLength={8} required value={next} onChange={(e) => setNext(e.target.value)} aria-label="New password" />
        </Field>
        <Field label="Confirm new password">
          <Input type="password" autoComplete="new-password" minLength={8} required value={confirm} onChange={(e) => setConfirm(e.target.value)} aria-label="Confirm new password" />
        </Field>
        {error && <Alert tone="error">{error}</Alert>}
        <div>
          <Button type="submit" loading={busy}>
            Update password
          </Button>
        </div>
      </form>
    </Card>
  );
}

function MfaCard() {
  const toast = useToast();
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enabled, setEnabled] = useState(false);

  async function begin() {
    setBusy(true);
    setError(null);
    try {
      setSetup(await api("/auth/mfa/setup", { method: "POST" }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start MFA setup.");
    } finally {
      setBusy(false);
    }
  }

  async function enable(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/auth/mfa/enable", { method: "POST", body: { totp_code: code.trim() } });
      setEnabled(true);
      setSetup(null);
      setCode("");
      toast.push("Multi-factor authentication enabled.", "success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not enable MFA.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card pad={false}>
      <CardHeader title="Multi-factor authentication" action={<Icon.Shield size={18} />} />
      <div className="card-pad stack gap-4">
        {enabled ? (
          <Alert tone="success">MFA is enabled on your account.</Alert>
        ) : !setup ? (
          <>
            <p className="muted text-sm">
              Protect the Super Admin account with a time-based one-time password (TOTP) from an
              authenticator app.
            </p>
            <div>
              <Button variant="secondary" onClick={begin} loading={busy}>
                Set up authenticator
              </Button>
            </div>
          </>
        ) : (
          <form className="stack gap-4" onSubmit={enable}>
            <Field label="Secret key" hint="Add this to your authenticator app, or use the URI below.">
              <Input readOnly value={setup.secret} className="mono" onFocus={(e) => e.currentTarget.select()} />
            </Field>
            <Field label="otpauth URI">
              <Input readOnly value={setup.otpauth_uri} className="mono text-xs" onFocus={(e) => e.currentTarget.select()} />
            </Field>
            <Field label="Verification code" hint="Enter the 6-digit code to confirm.">
              <Input inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="123456" aria-label="Verification code" />
            </Field>
            {error && <Alert tone="error">{error}</Alert>}
            <div>
              <Button type="submit" loading={busy} disabled={!code.trim()}>
                Enable MFA
              </Button>
            </div>
          </form>
        )}
        {error && !setup && <Alert tone="error">{error}</Alert>}
      </div>
    </Card>
  );
}
