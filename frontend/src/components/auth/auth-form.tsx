"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { PasswordField } from "@/components/auth/password-field";
import { passwordGuidance, passwordScore } from "@/components/auth/password-strength";
import { Icon } from "@/components/ui/icon";
import { login, signup } from "@/services/auth-api";

type AuthFormProps = Readonly<{ mode: "login" | "signup" }>;

export function AuthForm({ mode }: AuthFormProps) {
  const [password, setPassword] = useState("");
  const [notice, setNotice] = useState("");
  const [isPending, setIsPending] = useState(false);
  const router = useRouter();
  const isSignup = mode === "signup";
  const strength = passwordScore(password);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice("");
    setIsPending(true);
    const form = new FormData(event.currentTarget);
    try {
      const result = isSignup
        ? await signup({
            full_name: String(form.get("full_name")),
            email: String(form.get("email")),
            password: String(form.get("password")),
          })
        : await login({
            email: String(form.get("email")),
            password: String(form.get("password")),
          });
      router.push(result.next);
      router.refresh();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Something went wrong.");
    } finally {
      setIsPending(false);
    }
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit}>
      {isSignup && (
        <div className="form-field">
          <label htmlFor="name">Full name</label>
          <input id="full_name" name="full_name" type="text" autoComplete="name" placeholder="Maya Chen" minLength={2} maxLength={200} required />
        </div>
      )}
      <div className="form-field">
        <label htmlFor="email">Work email</label>
        <input id="email" name="email" type="email" autoComplete="email" placeholder="you@company.com" required />
      </div>
      <PasswordField
        id="password"
        label="Password"
        autoComplete={isSignup ? "new-password" : "current-password"}
        onChange={isSignup ? setPassword : undefined}
      />
      {isSignup ? (
        <div className="password-strength" aria-live="polite">
          <span aria-hidden="true">{[1, 2, 3].map((step) => <i className={step <= strength ? "active" : ""} key={step} />)}</span>
          <small>{passwordGuidance(strength)}</small>
        </div>
      ) : (
        <div className="form-options">
          <label className="check-field"><input type="checkbox" name="remember" /><span /> Keep me signed in</label>
          <button type="button" onClick={() => setNotice("Password recovery will be available when backend auth is connected.")}>Forgot password?</button>
        </div>
      )}
      {isSignup && (
        <label className="check-field check-field--terms">
          <input type="checkbox" name="terms" required />
          <span />
          <em>I agree to the Terms and Privacy Policy.</em>
        </label>
      )}
      <button className="auth-submit" type="submit" disabled={isPending}>
        {isPending ? "Please wait…" : isSignup ? "Create account" : "Sign in"}
        <Icon name="arrow" />
      </button>
      {notice && <p className="auth-notice" role="status"><Icon name="spark" />{notice}</p>}
      <p className="auth-switch">
        {isSignup ? "Already have a workspace?" : "New to ProjectBridge?"}{" "}
        <Link href={isSignup ? "/login" : "/signup"}>{isSignup ? "Sign in" : "Create an account"}</Link>
      </p>
    </form>
  );
}

