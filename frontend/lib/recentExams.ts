"use client";

/* Tracks exams created or opened in THIS browser, per institution.
   The backend exposes no staff "list exams" endpoint, so this is a local
   convenience index only — never a source of truth and never shared. */

export type RecentExam = { id: number; title: string; status: string; at: number };

const KEY = (institutionId: number) => `mm_recent_exams_${institutionId}`;

export function getRecentExams(institutionId: number): RecentExam[] {
  try {
    const raw = localStorage.getItem(KEY(institutionId));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as RecentExam[];
    return Array.isArray(parsed) ? parsed.sort((a, b) => b.at - a.at) : [];
  } catch {
    return [];
  }
}

export function rememberExam(institutionId: number, exam: { id: number; title: string; status: string }): void {
  try {
    const existing = getRecentExams(institutionId).filter((e) => e.id !== exam.id);
    const next = [{ ...exam, at: Date.now() }, ...existing].slice(0, 30);
    localStorage.setItem(KEY(institutionId), JSON.stringify(next));
  } catch {
    /* ignore storage errors */
  }
}

export function forgetExam(institutionId: number, id: number): void {
  try {
    localStorage.setItem(KEY(institutionId), JSON.stringify(getRecentExams(institutionId).filter((e) => e.id !== id)));
  } catch {
    /* ignore */
  }
}
