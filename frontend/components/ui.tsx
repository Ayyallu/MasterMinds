"use client";

/* MasterMinds shared UI component library.
   Thin, class-driven React wrappers over the design-system CSS in globals.css.
   No external UI dependency. */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { Icon } from "./icons";

/* ----------------------------------------------------------------- utils */
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/* ----------------------------------------------------------------- Button */
type ButtonVariant =
  | "primary"
  | "accent"
  | "secondary"
  | "ghost"
  | "danger"
  | "success";

export function Button({
  variant = "primary",
  size,
  block,
  loading,
  icon,
  className,
  children,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: "sm" | "lg";
  block?: boolean;
  loading?: boolean;
  icon?: ReactNode;
}) {
  return (
    <button
      className={cx(
        "btn",
        `btn-${variant}`,
        size === "sm" && "btn-sm",
        size === "lg" && "btn-lg",
        block && "btn-block",
        className,
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <span className="spinner" style={{ borderTopColor: "currentColor" }} /> : icon}
      {children}
    </button>
  );
}

/* ----------------------------------------------------------------- Card */
export function Card({
  interactive,
  pad = true,
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { interactive?: boolean; pad?: boolean }) {
  return (
    <div
      className={cx("card", pad && "card-pad", interactive && "card-interactive", className)}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, action }: { title: ReactNode; action?: ReactNode }) {
  return (
    <div className="card-header">
      <span className="card-title">{title}</span>
      {action}
    </div>
  );
}

/* ----------------------------------------------------------------- Stat */
export function Stat({
  label,
  value,
  icon,
  foot,
}: {
  label: ReactNode;
  value: ReactNode;
  icon?: ReactNode;
  foot?: ReactNode;
}) {
  return (
    <div className="stat">
      <div className="row between">
        <span className="stat-label">{label}</span>
        {icon && <span className="stat-icon">{icon}</span>}
      </div>
      <span className="stat-value">{value}</span>
      {foot && <span className="stat-foot">{foot}</span>}
    </div>
  );
}

/* ----------------------------------------------------------------- Badge */
type BadgeTone = "neutral" | "accent" | "success" | "warning" | "danger" | "info";
export function Badge({
  tone = "neutral",
  dot,
  children,
  className,
}: {
  tone?: BadgeTone;
  dot?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span className={cx("badge", `badge-${tone}`, dot && "badge-dot", className)}>{children}</span>
  );
}

/* Map arbitrary status strings to a badge tone + readable label. */
export function statusTone(status: string): BadgeTone {
  const s = status.toLowerCase();
  if (["approved", "active", "published", "ok", "completed", "submitted", "live"].includes(s))
    return "success";
  if (["pending", "in_review", "awaiting_approval", "draft", "in_progress", "scheduled"].includes(s))
    return "warning";
  if (["rejected", "disabled", "cancelled", "expired", "unavailable", "error"].includes(s))
    return "danger";
  if (["approved_global", "central", "global"].includes(s)) return "accent";
  return "neutral";
}
export function humanize(s: string): string {
  return s.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge tone={statusTone(status)} dot>
      {humanize(status)}
    </Badge>
  );
}

/* ----------------------------------------------------------------- Field / inputs */
export function Field({
  label,
  hint,
  error,
  children,
  htmlFor,
}: {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  children: ReactNode;
  htmlFor?: string;
}) {
  return (
    <div className="field">
      {label && (
        <label className="label" htmlFor={htmlFor}>
          {label}
        </label>
      )}
      {children}
      {error ? (
        <span className="hint" style={{ color: "var(--danger-700)" }}>
          {error}
        </span>
      ) : (
        hint && <span className="hint">{hint}</span>
      )}
    </div>
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cx("input", props.className)} {...props} />;
}
export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cx("textarea", props.className)} {...props} />;
}
export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cx("select", props.className)} {...props} />;
}

/* A labelled input wired together with a generated id for accessibility. */
export function LabeledInput({
  label,
  hint,
  error,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: ReactNode; hint?: ReactNode; error?: ReactNode }) {
  const id = useId();
  return (
    <Field label={label} hint={hint} error={error} htmlFor={id}>
      <Input id={id} aria-label={typeof label === "string" ? label : undefined} {...props} />
    </Field>
  );
}

/* ----------------------------------------------------------------- Table */
export function Table({ columns, children }: { columns: ReactNode[]; children: ReactNode }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            {columns.map((c, i) => (
              <th key={i}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

/* ----------------------------------------------------------------- Tabs */
export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
}: {
  tabs: { id: T; label: ReactNode }[];
  value: T;
  onChange: (id: T) => void;
}) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={value === t.id}
          className="tab"
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

/* ----------------------------------------------------------------- Alert */
export function Alert({
  tone = "info",
  children,
}: {
  tone?: "error" | "success" | "warning" | "info";
  children: ReactNode;
}) {
  const icon = {
    error: <Icon.AlertCircle size={18} />,
    success: <Icon.CheckCircle size={18} />,
    warning: <Icon.AlertTriangle size={18} />,
    info: <Icon.Info size={18} />,
  }[tone];
  return (
    <div className={cx("alert", `alert-${tone}`)} role={tone === "error" ? "alert" : "status"}>
      {icon}
      <div>{children}</div>
    </div>
  );
}

/* ----------------------------------------------------------------- States */
export function Spinner({ large }: { large?: boolean }) {
  return <span className={cx("spinner", large && "spinner-lg")} aria-hidden="true" />;
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="state" role="status">
      <Spinner large />
      <span>{label}</span>
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon?: ReactNode;
  title: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="state">
      <span className="state-icon">{icon ?? <Icon.Inbox size={24} />}</span>
      <span className="state-title">{title}</span>
      {children && <p style={{ maxWidth: 420 }}>{children}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ title = "Something went wrong", children, action }: {
  title?: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="state">
      <span className="state-icon" style={{ background: "var(--danger-50)", color: "var(--danger-500)" }}>
        <Icon.AlertTriangle size={24} />
      </span>
      <span className="state-title">{title}</span>
      {children && <p style={{ maxWidth: 420 }}>{children}</p>}
      {action}
    </div>
  );
}

/* ----------------------------------------------------------------- Dialog */
export function Dialog({
  open,
  onClose,
  title,
  children,
  actions,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  actions?: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="dialog-overlay" onMouseDown={onClose}>
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === "string" ? title : undefined}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="dialog-pad">
          <div className="row between" style={{ marginBottom: "var(--s-2)" }}>
            <h3 className="dialog-title" style={{ margin: 0 }}>
              {title}
            </h3>
            <button className="btn btn-ghost btn-icon btn-sm" onClick={onClose} aria-label="Close dialog">
              <Icon.Close size={18} />
            </button>
          </div>
          <div>{children}</div>
          {actions && <div className="dialog-actions">{actions}</div>}
        </div>
      </div>
    </div>
  );
}

/* A confirmation dialog built on Dialog. */
export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = "Confirm",
  tone = "primary",
  loading,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: ReactNode;
  message: ReactNode;
  confirmLabel?: string;
  tone?: ButtonVariant;
  loading?: boolean;
}) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title}
      actions={
        <>
          <Button variant="secondary" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button variant={tone} onClick={onConfirm} loading={loading}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p className="muted">{message}</p>
    </Dialog>
  );
}

/* ----------------------------------------------------------------- Toasts */
type Toast = { id: number; tone: "success" | "error" | "info"; message: string };
type ToastCtx = { push: (message: string, tone?: Toast["tone"]) => void };
const ToastContext = createContext<ToastCtx | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const idRef = useRef(0);

  const remove = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  const push = useCallback(
    (message: string, tone: Toast["tone"] = "info") => {
      const id = ++idRef.current;
      setToasts((t) => [...t, { id, tone, message }]);
      setTimeout(() => remove(id), 5000);
    },
    [remove],
  );

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="toast-region" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={cx("toast", `toast-${t.tone}`)} role="status">
            {t.tone === "success" ? (
              <Icon.CheckCircle size={18} />
            ) : t.tone === "error" ? (
              <Icon.AlertCircle size={18} />
            ) : (
              <Icon.Info size={18} />
            )}
            <span className="grow">{t.message}</span>
            <button onClick={() => remove(t.id)} aria-label="Dismiss notification">
              <Icon.Close size={16} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastCtx {
  const ctx = useContext(ToastContext);
  if (!ctx) return { push: () => undefined };
  return ctx;
}

/* ----------------------------------------------------------------- PageHeader */
export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        <h1 className="page-title">{title}</h1>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="row gap-3 wrap">{actions}</div>}
    </div>
  );
}

/* ----------------------------------------------------------------- useAsync */
export type AsyncState<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
};

/** Runs an async loader on mount and whenever `deps` change. */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setData(await loader());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load data.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, loading, error, reload };
}

/** Convenience wrapper that renders loading / error / empty / content states. */
export function AsyncView<T>({
  state,
  children,
  empty,
  isEmpty,
  loadingLabel,
}: {
  state: AsyncState<T>;
  children: (data: T) => ReactNode;
  empty?: ReactNode;
  isEmpty?: (data: T) => boolean;
  loadingLabel?: string;
}) {
  if (state.loading && state.data === null) return <LoadingState label={loadingLabel} />;
  if (state.error && state.data === null)
    return (
      <ErrorState>
        {state.error}
        <div style={{ marginTop: "var(--s-3)" }}>
          <Button variant="secondary" size="sm" onClick={() => void state.reload()}>
            Try again
          </Button>
        </div>
      </ErrorState>
    );
  if (state.data === null) return null;
  if (empty && isEmpty && isEmpty(state.data)) return <>{empty}</>;
  return <>{children(state.data)}</>;
}
