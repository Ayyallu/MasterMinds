import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Inter, Plus_Jakarta_Sans } from "next/font/google";
import { ToastProvider } from "@/components/ui";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

// Display face for headings, stats and brand marks.
const display = Plus_Jakarta_Sans({
  subsets: ["latin"],
  display: "swap",
  weight: ["500", "600", "700", "800"],
  variable: "--font-display-face",
});

export const metadata: Metadata = {
  title: "MasterMinds — Online Exam Platform",
  description:
    "A secure online examination platform for schools and colleges.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${display.variable}`}>
      <body>
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
