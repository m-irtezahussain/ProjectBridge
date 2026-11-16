import type { Metadata } from "next";

import { AuthForm } from "@/components/auth/auth-form";
import { AuthShell } from "@/components/auth/auth-shell";

export const metadata: Metadata = {
  title: "Create your workspace — ProjectBridge",
  description: "Create a ProjectBridge workspace for your team and AI assistants.",
};

export default function SignupPage() {
  return (
    <AuthShell
      eyebrow="Create your workspace"
      title="Build a shared memory for your projects."
      description="Bring your team, source documents, and trusted assistants into one secure operational layer."
    >
      <AuthForm mode="signup" />
    </AuthShell>
  );
}

