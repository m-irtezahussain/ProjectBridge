import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { AuthShell } from "@/components/auth/auth-shell";
import { BusinessRegistrationForm } from "@/components/auth/business-registration-form";
import { getSessionStatus } from "@/services/server-auth";

export const metadata: Metadata = {
  title: "Register your business — ProjectBridge",
  description: "Finish setting up your ProjectBridge workspace.",
};

export default async function BusinessRegistrationPage() {
  const session = await getSessionStatus();
  if (!session.authenticated) {
    redirect("/login");
  }
  if (session.has_business) {
    redirect("/dashboard");
  }

  return (
    <AuthShell
      eyebrow="One last step"
      title="Name the workspace your team will share."
      description="Your business boundary keeps projects, documents, search context, and assistant access isolated from every other organization."
    >
      <BusinessRegistrationForm />
    </AuthShell>
  );
}
