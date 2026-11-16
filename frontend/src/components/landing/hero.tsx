import { ProductPreview } from "@/components/landing/product-preview";
import { Icon } from "@/components/ui/icon";
import type { DisplayStatus } from "@/types/status";

type HeroProps = Readonly<{ status: DisplayStatus }>;

export function Hero({ status }: HeroProps) {
  return (
    <section className="hero shell" aria-labelledby="hero-title">
      <div className="hero__copy">
        <div className="eyebrow reveal">Built for teams and their AI</div>
        <h1 id="hero-title" className="reveal reveal--delay-1">
          The operational layer between <em>people</em> and AI.
        </h1>
        <p className="hero__lede reveal reveal--delay-2">
          Plan work, capture source documents, and let any MCP-compatible assistant
          move projects forward—with the same permissions, context, and audit trail.
        </p>
        <div className="hero__actions reveal reveal--delay-3">
          <Link className="button button--primary" href="/signup">
            Start building
            <Icon name="arrow" />
          </Link>
          <a className="button button--text" href="#product">
            Explore the platform
            <Icon name="chevron" />
          </a>
        </div>
        <div className="hero__proof reveal reveal--delay-3" aria-label="Platform qualities">
          <span><Icon name="check" /> Tenant isolated</span>
          <span><Icon name="check" /> Source traceable</span>
          <span><Icon name="check" /> MCP native</span>
        </div>
      </div>
      <ProductPreview status={status} />
    </section>
  );
}

import Link from "next/link";

