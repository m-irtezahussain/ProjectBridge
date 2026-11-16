import { Brand } from "@/components/landing/brand";
import { Icon } from "@/components/ui/icon";

export function SiteFooter() {
  return (
    <footer className="site-footer" id="contact">
      <div className="shell cta-panel scroll-reveal">
        <span className="eyebrow">Build the bridge</span>
        <h2>Give every project<br />a living memory.</h2>
        <p>ProjectBridge is taking shape. Join the early access list and help define what comes next.</p>
        <Link className="button button--light" href="/signup">
          Request early access <Icon name="arrow" />
        </Link>
      </div>
      <div className="shell footer-bottom">
        <Brand />
        <p>Project operations for people and AI.</p>
        <div><a href="#product">Product</a><a href="#security">Security</a><a href="#top">Back to top ↑</a></div>
      </div>
    </footer>
  );
}

import Link from "next/link";

