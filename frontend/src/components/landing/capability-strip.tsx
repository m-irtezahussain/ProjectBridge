const capabilities = [
  "Project context",
  "Task orchestration",
  "Document intelligence",
  "Semantic search",
  "Scoped MCP access",
];

export function CapabilityStrip() {
  return (
    <section className="capability-strip" aria-label="Platform capabilities">
      <div className="shell capability-strip__inner">
        <span className="capability-strip__label">One shared context layer</span>
        <div className="capability-strip__items">
          {capabilities.map((item) => <span key={item}>{item}</span>)}
        </div>
      </div>
    </section>
  );
}

