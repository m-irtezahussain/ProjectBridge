"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import { Icon } from "@/components/ui/icon";
import { registerBusiness } from "@/services/auth-api";

export function BusinessRegistrationForm() {
  const [notice, setNotice] = useState("");
  const [isPending, setIsPending] = useState(false);
  const router = useRouter();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice("");
    setIsPending(true);
    const form = new FormData(event.currentTarget);
    try {
      const result = await registerBusiness(String(form.get("name")));
      router.replace(result.next);
      router.refresh();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Something went wrong.");
    } finally {
      setIsPending(false);
    }
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit}>
      <div className="form-field">
        <label htmlFor="business-name">Business name</label>
        <input
          id="business-name"
          name="name"
          type="text"
          autoComplete="organization"
          placeholder="Acme Studio"
          minLength={2}
          maxLength={200}
          required
          autoFocus
        />
      </div>
      <p className="form-hint">This becomes your tenant-isolated workspace. You can invite your team after signing in.</p>
      <button className="auth-submit" type="submit" disabled={isPending}>
        {isPending ? "Creating workspace…" : "Register business"}
        <Icon name="arrow" />
      </button>
      {notice && <p className="auth-notice" role="alert"><Icon name="spark" />{notice}</p>}
    </form>
  );
}
