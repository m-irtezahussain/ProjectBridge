import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "ProjectBridge — Project operations for people and AI",
  description:
    "Plan work, turn source documents into traceable action, and connect any MCP-compatible assistant to the same secure project context.",
  keywords: ["project management", "MCP server", "AI project management", "document intelligence"],
  openGraph: {
    title: "ProjectBridge — Project operations for people and AI",
    description: "One secure operational layer for your team, your projects, and your AI assistants.",
    type: "website",
  },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" id="top">
      <body>{children}</body>
    </html>
  );
}

