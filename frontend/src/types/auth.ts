export type NavigationResponse = Readonly<{
  message: string;
  next: string;
}>;

export type SessionStatus = Readonly<{
  authenticated: boolean;
  has_business: boolean;
  full_name: string | null;
  email: string | null;
  next: string;
}>;
