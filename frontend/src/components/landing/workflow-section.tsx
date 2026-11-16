import { Icon } from "@/components/ui/icon";

const steps = [
  {
    number: "01",
    title: "Connect with scoped access",
    body: "A user authorizes their assistant for one business with only the read or write scopes it needs.",
  },
  {
    number: "02",
    title: "Bring the project into context",
    body: "The assistant retrieves relevant projects, tasks, roles, and knowledge through compact MCP tools.",
  },
  {
    number: "03",
    title: "Turn input into structured work",
    body: "Files stay immutable while extracted content becomes traceable tasks, updates, and searchable knowledge.",
  },
];

export function WorkflowSection() {
  return (
    <section className="workflow-section" id="workflow" aria-labelledby="workflow-title">
      <div className="shell workflow-layout">
        <div className="workflow-copy scroll-reveal">
          <span className="eyebrow">One core · Two interfaces</span>
          <h2 id="workflow-title">Your app and your assistant finally speak the same language.</h2>
          <p>
            The web application and MCP server sit on the same permission-aware backend.
            Work stays consistent no matter where it starts.
          </p>
          <a className="text-link" href="#contact">See what you can build <Icon name="arrow" /></a>
        </div>
        <div className="workflow-steps">
          {steps.map((step) => (
            <article className="workflow-step scroll-reveal" key={step.number}>
              <span>{step.number}</span>
              <div><h3>{step.title}</h3><p>{step.body}</p></div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

