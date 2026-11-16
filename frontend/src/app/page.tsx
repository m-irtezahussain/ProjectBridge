import { CapabilityStrip } from "@/components/landing/capability-strip";
import { Hero } from "@/components/landing/hero";
import { ProductSection } from "@/components/landing/product-section";
import { SecuritySection } from "@/components/landing/security-section";
import { SiteFooter } from "@/components/landing/site-footer";
import { SiteHeader } from "@/components/landing/site-header";
import { WorkflowSection } from "@/components/landing/workflow-section";
import { getServiceStatus } from "@/services/api";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const status = await getServiceStatus();

  return (
    <>
      <a className="skip-link" href="#main-content">Skip to content</a>
      <div className="scroll-progress" aria-hidden="true" />
      <SiteHeader />
      <main id="main-content">
        <Hero status={status} />
        <CapabilityStrip />
        <ProductSection />
        <WorkflowSection />
        <SecuritySection />
      </main>
      <SiteFooter />
    </>
  );
}

