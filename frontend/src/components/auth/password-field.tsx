"use client";

import { useState } from "react";

type PasswordFieldProps = Readonly<{
  autoComplete: "current-password" | "new-password";
  id: string;
  label: string;
  onChange?: (value: string) => void;
}>;

export function PasswordField({ autoComplete, id, label, onChange }: PasswordFieldProps) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="form-field">
      <div className="form-label-row">
        <label htmlFor={id}>{label}</label>
        <button
          className="password-toggle"
          type="button"
          aria-controls={id}
          aria-pressed={visible}
          onClick={() => setVisible((current) => !current)}
        >
          {visible ? "Hide" : "Show"}
        </button>
      </div>
      <input
        id={id}
        name="password"
        type={visible ? "text" : "password"}
        autoComplete={autoComplete}
        minLength={8}
        maxLength={128}
        placeholder="At least 8 characters"
        required
        onChange={(event) => onChange?.(event.target.value)}
      />
    </div>
  );
}

