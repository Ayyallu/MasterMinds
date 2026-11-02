"use client";

import { useCallback, useEffect, useState } from "react";

import { api, clearTokens, getToken, setRefreshToken, setToken } from "@/lib/api";

type Me = {
  id: number;
  email: string | null;
  full_name: string;
  is_super_admin: boolean;
  roles: string[];
  institution_ids: number[];
};

type Registration = {
  id: number;
  institution_name: string;
  requested_code: string;
  contact_email: string;
  status: string;
};

const card: React.CSSProperties = {
  border: "1px solid #d1d5db",
  borderRadius: 8,
  padding: "1rem",
  marginBottom: "1rem",
  maxWidth: 640,
};

export default function AdminPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadMe = useCallback(async () => {
    if (!getToken()) {
      setMe(null);
      return;
    }
    try {
      setMe(await api<Me>("/auth/me"));
    } catch {
      clearTokens();
      setMe(null);
    }
  }, []);

  useEffect(() => {
    loadMe();
  }, [loadMe]);

  if (!me) return <LoginForm onDone={loadMe} error={error} setError={setError} />;

  return (
    <main>
      <h1>Admin</h1>
      <p>
        Signed in as <strong>{me.email ?? me.full_name}</strong>{" "}
        {me.is_super_admin ? "(Super Admin)" : `(${me.roles.join(", ")})`}{" "}
        <button
          onClick={() => {
            clearTokens();
            setMe(null);
          }}
        >
          Sign out
        </button>
      </p>
      {me.is_super_admin ? (
        <Registrations />
      ) : (
        <InstitutionAdmin institutionIds={me.institution_ids} />
      )}
    </main>
  );
}

function LoginForm({
  onDone,
  error,
  setError,
}: {
  onDone: () => void;
  error: string | null;
  setError: (v: string | null) => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const res = await api<{ access_token: string; refresh_token: string }>("/auth/login", {
        method: "POST",
        auth: false,
        body: { email, password },
      });
      setToken(res.access_token);
      setRefreshToken(res.refresh_token);
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    }
  }

  return (
    <main>
      <h1>Admin sign in</h1>
      <form onSubmit={submit} style={card}>
        <div style={{ marginBottom: 8 }}>
          <input
            type="email"
            aria-label="Email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={{ width: "100%", padding: 8 }}
          />
        </div>
        <div style={{ marginBottom: 8 }}>
          <input
            type="password"
            aria-label="Password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{ width: "100%", padding: 8 }}
          />
        </div>
        <button type="submit">Sign in</button>
        {error && <p style={{ color: "#b91c1c" }}>{error}</p>}
      </form>
    </main>
  );
}

function Registrations() {
  const [rows, setRows] = useState<Registration[]>([]);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    const data = await api<Registration[]>(
      "/admin/registrations?status_filter=pending",
    );
    setRows(data);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function approve(r: Registration) {
    setMsg(null);
    try {
      const res = await api<{ debug_admin_temp_password?: string }>(
        `/admin/registrations/${r.id}/approve`,
        {
          method: "POST",
          body: {
            admin_email: r.contact_email,
            admin_full_name: `${r.institution_name} Admin`,
          },
        },
      );
      setMsg(
        `Approved ${r.institution_name}.` +
          (res.debug_admin_temp_password
            ? ` Temp password: ${res.debug_admin_temp_password}`
            : ""),
      );
      load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Approve failed");
    }
  }

  return (
    <section>
      <h2>Pending institution registrations</h2>
      {rows.length === 0 && <p>None pending.</p>}
      {rows.map((r) => (
        <div key={r.id} style={card}>
          <strong>{r.institution_name}</strong> ({r.requested_code}) —{" "}
          {r.contact_email}
          <div style={{ marginTop: 8 }}>
            <button onClick={() => approve(r)}>Approve</button>
          </div>
        </div>
      ))}
      {msg && <p>{msg}</p>}
    </section>
  );
}

function InstitutionAdmin({ institutionIds }: { institutionIds: number[] }) {
  const institutionId = institutionIds[0];
  const [name, setName] = useState("");
  const [classGroups, setClassGroups] = useState<{ id: number; name: string }[]>(
    [],
  );
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!institutionId) return;
    setClassGroups(
      await api<{ id: number; name: string }[]>(
        `/institutions/${institutionId}/class-groups`,
      ),
    );
  }, [institutionId]);

  useEffect(() => {
    load();
  }, [load]);

  async function addClassGroup(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    try {
      await api(`/institutions/${institutionId}/class-groups`, {
        method: "POST",
        body: { name },
      });
      setName("");
      load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Create failed");
    }
  }

  if (!institutionId) return <p>No institution assigned.</p>;

  return (
    <section>
      <h2>Classes / sections / batches</h2>
      <form onSubmit={addClassGroup} style={card}>
        <input
          aria-label="Class group name"
          placeholder="Class group name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          style={{ padding: 8, marginRight: 8 }}
        />
        <button type="submit">Add</button>
        {msg && <p style={{ color: "#b91c1c" }}>{msg}</p>}
      </form>
      <ul>
        {classGroups.map((c) => (
          <li key={c.id}>{c.name}</li>
        ))}
      </ul>
    </section>
  );
}
