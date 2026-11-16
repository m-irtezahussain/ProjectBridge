import Link from "next/link";

import { Brand } from "@/components/landing/brand";
import { Icon } from "@/components/ui/icon";

const links = [
  { href: "#product", label: "Product" },
  { href: "#workflow", label: "How it works" },
  { href: "#security", label: "Security" },
];

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="shell site-header__inner">
        <Brand />
        <nav className="site-nav" aria-label="Primary navigation">
          {links.map((link) => (
            <a key={link.href} href={link.href}>{link.label}</a>
          ))}
        </nav>
        <div className="header-actions">
          <Link className="header-login" href="/login">Log in</Link>
          <Link className="button button--compact button--ghost header-cta" href="/signup">
            Get started <Icon name="arrow" />
          </Link>
        </div>
      </div>
    </header>
  );
}

