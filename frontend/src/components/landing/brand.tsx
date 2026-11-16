import Link from "next/link";

export function Brand() {
  return (
    <Link className="brand" href="/" aria-label="ProjectBridge home">
      <svg className="brand__mark" viewBox="0 0 32 32" aria-hidden="true">
        <path d="M5 8.5h11a5.5 5.5 0 0 1 0 11H9" />
        <path d="M27 23.5H16a5.5 5.5 0 0 1 0-11h7" />
        <circle cx="5" cy="8.5" r="2" />
        <circle cx="27" cy="23.5" r="2" />
      </svg>
      <span>ProjectBridge</span>
    </Link>
  );
}

