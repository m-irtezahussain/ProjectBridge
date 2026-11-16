"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { logout } from "@/services/auth-api";

export function LogoutButton() {
  const [pending, setPending] = useState(false);
  const router = useRouter();

  async function handleLogout() {
    setPending(true);
    try {
      const result = await logout();
      router.replace(result.next);
      router.refresh();
    } finally {
      setPending(false);
    }
  }

  return <button className="dashboard-logout" type="button" disabled={pending} onClick={handleLogout}>{pending ? "Signing out…" : "Sign out"}</button>;
}
