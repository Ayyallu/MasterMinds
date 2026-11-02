/* Lightweight inline-SVG icon set (no external dependency).
   Stroke icons, 1.75 weight, inherit currentColor. 24x24 viewBox. */
import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function Svg({ size = 18, children, ...props }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  );
}

export const Icon = {
  Dashboard: (p: IconProps) => (
    <Svg {...p}>
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </Svg>
  ),
  Building: (p: IconProps) => (
    <Svg {...p}>
      <rect x="4" y="3" width="16" height="18" rx="1.5" />
      <path d="M9 7h2M9 11h2M9 15h2M13 7h2M13 11h2M13 15h2M9 21v-3h6v3" />
    </Svg>
  ),
  Users: (p: IconProps) => (
    <Svg {...p}>
      <circle cx="9" cy="8" r="3.2" />
      <path d="M3.5 20a5.5 5.5 0 0 1 11 0" />
      <path d="M16 5.2a3.2 3.2 0 0 1 0 5.6M17.5 14.5A5.5 5.5 0 0 1 20.5 20" />
    </Svg>
  ),
  User: (p: IconProps) => (
    <Svg {...p}>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 20a7 7 0 0 1 14 0" />
    </Svg>
  ),
  Book: (p: IconProps) => (
    <Svg {...p}>
      <path d="M5 4.5A2.5 2.5 0 0 1 7.5 2H19v16H7.5A2.5 2.5 0 0 0 5 20.5z" />
      <path d="M5 20.5A2.5 2.5 0 0 1 7.5 18H19v4H7.5A2.5 2.5 0 0 1 5 20.5z" />
    </Svg>
  ),
  FileText: (p: IconProps) => (
    <Svg {...p}>
      <path d="M6 2h8l4 4v16H6z" />
      <path d="M14 2v4h4" />
      <path d="M9 12h6M9 16h6M9 8h2" />
    </Svg>
  ),
  ClipboardCheck: (p: IconProps) => (
    <Svg {...p}>
      <rect x="5" y="4" width="14" height="18" rx="2" />
      <path d="M9 4V3a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1" />
      <path d="M9 13l2 2 4-4" />
    </Svg>
  ),
  Sparkles: (p: IconProps) => (
    <Svg {...p}>
      <path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6z" />
      <path d="M18 14l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z" />
    </Svg>
  ),
  Chart: (p: IconProps) => (
    <Svg {...p}>
      <path d="M4 20V4M4 20h16" />
      <path d="M8 16v-4M12 16V7M16 16v-6" />
    </Svg>
  ),
  Calendar: (p: IconProps) => (
    <Svg {...p}>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M3 9h18M8 3v4M16 3v4" />
    </Svg>
  ),
  Clock: (p: IconProps) => (
    <Svg {...p}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </Svg>
  ),
  Settings: (p: IconProps) => (
    <Svg {...p}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" />
    </Svg>
  ),
  Logout: (p: IconProps) => (
    <Svg {...p}>
      <path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3" />
      <path d="M10 12H3M6 8l-3 4 3 4" />
    </Svg>
  ),
  Menu: (p: IconProps) => (
    <Svg {...p}>
      <path d="M4 6h16M4 12h16M4 18h16" />
    </Svg>
  ),
  Close: (p: IconProps) => (
    <Svg {...p}>
      <path d="M6 6l12 12M18 6L6 18" />
    </Svg>
  ),
  Check: (p: IconProps) => (
    <Svg {...p}>
      <path d="M5 12l4.5 4.5L19 7" />
    </Svg>
  ),
  CheckCircle: (p: IconProps) => (
    <Svg {...p}>
      <circle cx="12" cy="12" r="9" />
      <path d="M8 12l2.5 2.5L16 9" />
    </Svg>
  ),
  AlertCircle: (p: IconProps) => (
    <Svg {...p}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v4M12 16h.01" />
    </Svg>
  ),
  AlertTriangle: (p: IconProps) => (
    <Svg {...p}>
      <path d="M12 3l9 16H3z" />
      <path d="M12 9v4M12 17h.01" />
    </Svg>
  ),
  Info: (p: IconProps) => (
    <Svg {...p}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 8h.01" />
    </Svg>
  ),
  Plus: (p: IconProps) => (
    <Svg {...p}>
      <path d="M12 5v14M5 12h14" />
    </Svg>
  ),
  Search: (p: IconProps) => (
    <Svg {...p}>
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-3.5-3.5" />
    </Svg>
  ),
  ChevronRight: (p: IconProps) => (
    <Svg {...p}>
      <path d="M9 6l6 6-6 6" />
    </Svg>
  ),
  ChevronLeft: (p: IconProps) => (
    <Svg {...p}>
      <path d="M15 6l-6 6 6 6" />
    </Svg>
  ),
  ArrowRight: (p: IconProps) => (
    <Svg {...p}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </Svg>
  ),
  Shield: (p: IconProps) => (
    <Svg {...p}>
      <path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z" />
      <path d="M9 12l2 2 4-4" />
    </Svg>
  ),
  Inbox: (p: IconProps) => (
    <Svg {...p}>
      <path d="M3 13l2.5-8h13L21 13v5a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z" />
      <path d="M3 13h5l1 2h6l1-2h5" />
    </Svg>
  ),
  Upload: (p: IconProps) => (
    <Svg {...p}>
      <path d="M12 16V4M8 8l4-4 4 4" />
      <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
    </Svg>
  ),
  GraduationCap: (p: IconProps) => (
    <Svg {...p}>
      <path d="M12 4L2 9l10 5 10-5z" />
      <path d="M6 11v5c0 1 2.7 2.5 6 2.5s6-1.5 6-2.5v-5" />
    </Svg>
  ),
  Layers: (p: IconProps) => (
    <Svg {...p}>
      <path d="M12 3l9 5-9 5-9-5z" />
      <path d="M3 13l9 5 9-5M3 17l9 5 9-5" />
    </Svg>
  ),
  Globe: (p: IconProps) => (
    <Svg {...p}>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3c2.5 2.5 2.5 15 0 18M12 3c-2.5 2.5-2.5 15 0 18" />
    </Svg>
  ),
};

export type { IconProps };
