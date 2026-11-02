"use client";

import Link from "next/link";
import { useState } from "react";
import { api, setRefreshToken, setToken } from "@/lib/api";
import { AuthLayout } from "./AuthLayout";
import { Alert, Button, Field, Input } from "./ui";

/** Staff / admin sign-in (email + password, optional TOTP for Super Admin). */
export function StaffLogin({ onSignedIn }: { onSignedIn: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totp, setTotp] = useState("");
  const [mfaNeeded, setMfaNeeded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ access_token: string; refresh_token: string; mfa_required: boolean }>(
        "/auth/login",
        {
          method: "POST",
          auth: false,
          body: {
            email: email.trim(),
            password,
            ...(totp.trim() ? { totp_code: totp.trim() } : {}),
          },
        },
      );
      if (res.mfa_required) {
        setMfaNeeded(true);
        setError("Enter your authenticator code to continue.");
        return;
      }
      setToken(res.access_token);
      setRefreshToken(res.refresh_token);
      setPassword("");
      setTotp("");
      onSignedIn();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Sign in failed.";
      // The API intentionally returns 401 after validating the password when
      // MFA is enabled but no TOTP code was supplied. Reveal the code field
      // for that response so the user can retry without changing the API
      // authentication contract or weakening password verification.
      if (message.toLowerCase().includes("mfa code required")) {
        setMfaNeeded(true);
        setError("Enter your authenticator code to continue.");
      } else {
        setError(message);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout
      eyebrow="Staff portal"
      title="Sign in to your workspace"
      subtitle="For Super Admins, Institution Admins, Faculty and Reviewers."
      footer={
        <>
          Are you a student? <Link href="/student">Go to the student portal</Link>
        </>
      }
    >
      <form className="stack gap-4" onSubmit={submit}>
        <Field label="Email">
          <Input
            type="email"
            autoComplete="username"
            required
            value={email}
            aria-label="Email"
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@institution.edu"
          />
        </Field>
        <Field label="Password">
          <Input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            aria-label="Password"
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
          />
        </Field>
        {mfaNeeded && (
          <Field label="Authenticator code" hint="6-digit code from your authenticator app.">
            <Input
              inputMode="numeric"
              autoComplete="one-time-code"
              value={totp}
              aria-label="Authenticator code"
              onChange={(e) => setTotp(e.target.value)}
              placeholder="123456"
            />
          </Field>
        )}
        {error && <Alert tone={mfaNeeded ? "info" : "error"}>{error}</Alert>}
        <Button type="submit" block loading={busy} size="lg">
          Sign in
        </Button>
      </form>
    </AuthLayout>
  );
}
