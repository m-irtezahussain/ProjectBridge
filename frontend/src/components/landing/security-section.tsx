import { Icon } from "@/components/ui/icon";

const assurances = [
  "Repository-level tenant scoping",
  "Role and scope-based permissions",
  "Immutable original file storage",
  "Auditable app and MCP actions",
];

export function SecuritySection() {
  return (
    <section className="section shell" id="security" aria-labelledby="security-title">
      <div className="security-card scroll-reveal">
        <div className="security-card__copy">
          <span className="eyebrow eyebrow--dark">Security by architecture</span>
          <h2 id="security-title">Context should be useful.<br />Never porous.</h2>
          <p>
            Every business boundary is enforced below the interface layer. OCR and
            document text are treated as untrusted data, while every action remains
            permission checked and attributable.
          </p>
          <div className="assurance-grid">
            {assurances.map((item) => (
              <span key={item}><Icon name="check" />{item}</span>
            ))}
          </div>
        </div>
        <div className="security-visual" aria-hidden="true">
          <div className="security-orbit security-orbit--outer" />
          <div className="security-orbit security-orbit--inner" />
          <div className="security-core"><Icon name="lock" /><span>Tenant boundary</span></div>
          <span className="security-node security-node--one">WEB</span>
          <span className="security-node security-node--two">MCP</span>
          <span className="security-node security-node--three">RAG</span>
        </div>
      </div>
    </section>
  );
}

