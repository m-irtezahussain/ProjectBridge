export function passwordScore(password: string): number {
  if (password.length === 0) return 0;
  if (password.length < 15) return 1;
  if (password.length < 20) return 2;
  return 3;
}

export function passwordGuidance(score: number): string {
  if (score === 0) return "Use a memorable passphrase";
  if (score === 1) return "Keep going — 15 characters minimum";
  if (score === 2) return "Good length";
  return "Strong length";
}

