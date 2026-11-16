import { Icon, type IconName } from "@/components/ui/icon";
import type { ReactNode } from "react";

const features: Array<{
  icon: IconName;
  kicker: string;
  title: string;
  body: string;
  detail: ReactNode;
}> = [
  {
    icon: "command",
    kicker: "Work management",
    title: "A calm place for complex work.",
    body: "Shape projects, responsibilities, and timelines in a workspace designed to keep decisions close to execution.",
    detail: (
      <div className="mini-board" aria-hidden="true">
        <span><i className="dot dot--mint" /> Discovery <b>04</b></span>
        <span><i className="dot dot--violet" /> In progress <b>12</b></span>
        <span><i className="dot dot--amber" /> In review <b>03</b></span>
      </div>
    ),
  },
  {
    icon: "document",
    kicker: "Document intelligence",
    title: "Turn source material into accountable action.",
    body: "Preserve every original file, extract useful context, and trace generated tasks back to the exact source that informed them.",
    detail: (
      <div className="document-stack" aria-hidden="true">
        <span><Icon name="document" /><i>BRIEF</i></span>
        <span><Icon name="spark" /><i>EXTRACT</i></span>
        <span><Icon name="check" /><i>ACTION</i></span>
      </div>
    ),
  },
  {
    icon: "search",
    kicker: "Project memory",
    title: "Find the decision, not just the file.",
    body: "Search tasks, project history, and document knowledge semantically—inside the app or through an authorized assistant.",
    detail: (
      <div className="search-demo" aria-hidden="true">
        <Icon name="search" />
        <span>What changed in the launch plan?</span>
        <kbd>⌘ K</kbd>
      </div>
    ),
  },
];

export function ProductSection() {
  return (
    <section className="section shell" id="product" aria-labelledby="product-title">
      <div className="section-heading section-heading--split scroll-reveal">
        <div>
          <span className="eyebrow">A system that compounds</span>
          <h2 id="product-title">Every project becomes usable context.</h2>
        </div>
        <p>
          ProjectBridge connects planning, source material, and AI execution so your
          team spends less time reconstructing context and more time moving work forward.
        </p>
      </div>
      <div className="feature-grid">
        {features.map((feature, index) => (
          <article className={`feature-card feature-card--${index + 1} scroll-reveal`} key={feature.title}>
            <div className="feature-card__top">
              <span className="icon-chip"><Icon name={feature.icon} /></span>
              <span>{feature.kicker}</span>
            </div>
            <div className="feature-card__visual">{feature.detail}</div>
            <h3>{feature.title}</h3>
            <p>{feature.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

