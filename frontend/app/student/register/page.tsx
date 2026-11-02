"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import "../student.css";

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
    <main className="student-shell">
      <div className="student-topbar">
        <Link className="student-brand" href="/">MasterMinds</Link>
        <Link className="student-button secondary" href="/student">Student sign in</Link>
      </div>
      <section className="student-card" style={{ maxWidth: 620, margin: "3vh auto" }}>
        <p className="student-pill">STUDENT REGISTRATION</p>
        <h1>Create your student account</h1>
        {submitted ? (
          <div className="student-success" role="status">
            <strong>Registration received.</strong>
            <p>Your account is pending approval by your school or college administrator. You can sign in after it has been approved.</p>
            <Link href="/student">Go to student sign in</Link>
          </div>
        ) : (
          <>
            <p className="student-muted">Use the institution code and register number provided by your institution. Your account will remain pending until an administrator approves it.</p>
            <form className="student-form" onSubmit={submit}>
              <label className="student-label">Institution code
                <input className="student-input" required value={institutionCode} onChange={e => setInstitutionCode(e.target.value)} autoComplete="organization" />
              </label>
              <label className="student-label">Register number
                <input className="student-input" required value={registerNumber} onChange={e => setRegisterNumber(e.target.value)} autoComplete="username" />
              </label>
              <label className="student-label">Full name
                <input className="student-input" required maxLength={255} value={fullName} onChange={e => setFullName(e.target.value)} autoComplete="name" />
              </label>
              <label className="student-label">Email (optional)
                <input className="student-input" type="email" value={email} onChange={e => setEmail(e.target.value)} autoComplete="email" />
              </label>
              <label className="student-label">Password
                <input className="student-input" type="password" minLength={8} required value={password} onChange={e => setPassword(e.target.value)} autoComplete="new-password" />
                <span className="student-muted" style={{ fontWeight: 400 }}>Use at least 8 characters.</span>
              </label>
              {error && <p className="student-error" role="alert">{error}</p>}
              <button className="student-button" type="submit" disabled={busy}>{busy ? "Submitting…" : "Submit for approval"}</button>
            </form>
          </>
        )}
      </section>
    </main>
  );
}
