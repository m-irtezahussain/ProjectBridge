export type ServiceStatus = Readonly<{
  service: "projectbridge";
  status: "ok";
  version: string;
}>;

export type DisplayStatus = ServiceStatus | Readonly<{
  service: "projectbridge";
  status: "unavailable";
  version: string;
}>;

