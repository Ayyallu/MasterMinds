"use client";

import { useEffect, useState } from "react";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const POLL_INTERVAL_MS = 10_000;

type Status = "checking" | "ok" | "unavailable";

export default function HealthStatus() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    let active = true;

    async function poll() {
      try {
        const resp = await fetch(`${API_BASE_URL}/health`);
        const data = await resp.json();
        if (active) {
          setStatus(resp.ok && data.status === "ok" ? "ok" : "unavailable");
        }
      } catch {
        if (active) setStatus("unavailable");
      }
    }

    poll();
    const timer = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  const label =
    status === "ok"
      ? "Backend: online"
      : status === "unavailable"
        ? "Backend: unavailable"
        : "Backend: checking…";

  const color =
    status === "ok" ? "#15803d" : status === "unavailable" ? "#b91c1c" : "#6b7280";

  return (
    <p>
      <span
        aria-hidden
        style={{
          display: "inline-block",
          width: 10,
          height: 10,
          borderRadius: "50%",
          background: color,
          marginRight: 8,
        }}
      />
      <span role="status">{label}</span>
    </p>
  );
}
