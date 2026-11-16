import type { Metadata } from "next";

import { AuthForm } from "@/components/auth/auth-form";
import { AuthShell } from "@/components/auth/auth-shell";

export const metadata: Metadata = {
  title: "Sign in — ProjectBridge",
  description: "Sign in to your ProjectBridge workspace.",
};

export default function LoginPage() {
  return (
    <AuthShell
      eyebrow="Welcome back"
      title="Return to the work that matters."
      description="Sign in to your workspace and pick up with the same project context your team and assistants share."
    >
      <AuthForm mode="login" />
    </AuthShell>
  );
}

