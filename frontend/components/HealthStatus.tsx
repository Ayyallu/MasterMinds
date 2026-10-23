"use client";

import { useEffect, useRef, useState } from "react";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const BASE_INTERVAL_MS = 10_000;
const MAX_INTERVAL_MS = 60_000;
const REQUEST_TIMEOUT_MS = 5_000;

type Status = "checking" | "ok" | "unavailable";

export default function HealthStatus() {
  const [status, setStatus] = useState<Status>("checking");

  // Mutable refs so the single polling loop can read current state without
  // being re-created on every change.
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inFlightRef = useRef<AbortController | null>(null);
  const failuresRef = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    const clearTimer = () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };

    const scheduleNext = () => {
      clearTimer();
      if (document.hidden) return; // don't poll while the tab is hidden
      // Exponential backoff on consecutive failures, capped.
      const backoff = Math.min(
        BASE_INTERVAL_MS * 2 ** Math.max(0, failuresRef.current - 1),
        MAX_INTERVAL_MS,
      );
      const delay = failuresRef.current > 0 ? backoff : BASE_INTERVAL_MS;
      timerRef.current = setTimeout(poll, delay);
    };

    async function poll() {
      // Prevent overlapping requests: abort nothing, just skip if one is live.
      if (inFlightRef.current) return;
      if (document.hidden) return;

      const controller = new AbortController();
      inFlightRef.current = controller;
      const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

      try {
        const resp = await fetch(`${API_BASE_URL}/health`, {
          signal: controller.signal,
        });
        const data = await resp.json().catch(() => null);
        if (!mountedRef.current) return;
        if (resp.ok && data?.status === "ok") {
          failuresRef.current = 0;
          setStatus("ok");
        } else {
          failuresRef.current += 1;
          setStatus("unavailable");
        }
      } catch {
        if (!mountedRef.current) return;
        failuresRef.current += 1;
        setStatus("unavailable");
      } finally {
        clearTimeout(timeout);
        inFlightRef.current = null;
        if (mountedRef.current) scheduleNext();
      }
    }

    const onVisibility = () => {
      if (document.hidden) {
        clearTimer();
      } else {
        // Refresh immediately when the tab becomes visible again.
        poll();
      }
    };

    document.addEventListener("visibilitychange", onVisibility);
    poll();

    return () => {
      mountedRef.current = false;
      document.removeEventListener("visibilitychange", onVisibility);
      clearTimer();
      inFlightRef.current?.abort();
      inFlightRef.current = null;
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
