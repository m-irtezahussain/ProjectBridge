import { describe, expect, it } from "vitest";

import { passwordGuidance, passwordScore } from "../src/components/auth/password-strength";

describe("signup password feedback", () => {
  it("requires a password-only account to use at least 15 characters", () => {
    expect(passwordScore("fourteen-chars!".slice(0, 14))).toBe(1);
    expect(passwordGuidance(1)).toContain("15 characters minimum");
  });

  it("rewards longer passphrases without composition rules", () => {
    expect(passwordScore("a long easy passphrase to remember")).toBe(3);
    expect(passwordGuidance(3)).toBe("Strong length");
  });
});

