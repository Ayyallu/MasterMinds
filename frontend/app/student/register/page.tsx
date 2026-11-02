"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { AuthLayout } from "@/components/AuthLayout";
import { Alert, Button, Field, Input } from "@/components/ui";

export default function StudentRegistrationPage() {
  const [institutionCode, setInstitutionCode] = useState("");
  const [registerNumber, setRegisterNumber] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/students/self-register", {
        method: "POST",
        auth: false,
        body: {
          institution_code: institutionCode.trim(),
          register_number: registerNumber.trim(),
          full_name: fullName.trim(),
          password,
          ...(email.trim() ? { email: email.trim() } : {}),
        },
      });
      setSubmitted(true);
      setPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout
      eyebrow="Student registration"
      title="Create your student account"
      subtitle="Use the institution code and register number provided by your institution."
      footer={
        <>
          Already registered? <Link href="/student">Sign in</Link>
        </>
      }
    >
      {submitted ? (
        <div className="stack gap-4">
          <Alert tone="success">
            <strong>Registration received.</strong> Your account is pending approval by your school or
            college administrator. You can sign in once it has been approved.
          </Alert>
          <Link href="/student" className="btn btn-primary btn-block">
            Go to student sign in
          </Link>
        </div>
      ) : (
        <form className="stack gap-4" onSubmit={submit}>
          <Field label="Institution code">
            <Input required value={institutionCode} onChange={(e) => setInstitutionCode(e.target.value)} autoComplete="organization" aria-label="Institution code" />
          </Field>
          <Field label="Register number">
            <Input required value={registerNumber} onChange={(e) => setRegisterNumber(e.target.value)} autoComplete="username" aria-label="Register number" />
          </Field>
          <Field label="Full name">
            <Input required maxLength={255} value={fullName} onChange={(e) => setFullName(e.target.value)} autoComplete="name" aria-label="Full name" />
          </Field>
          <Field label="Email (optional)">
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" aria-label="Email" />
          </Field>
          <Field label="Password" hint="Use at least 8 characters.">
            <Input type="password" minLength={8} required value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" aria-label="Password" />
          </Field>
          {error && <Alert tone="error">{error}</Alert>}
          <Button type="submit" block size="lg" loading={busy}>
            Submit for approval
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
