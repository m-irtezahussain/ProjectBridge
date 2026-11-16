import { ServiceStatus } from "@/components/service-status";
import { Icon, type IconName } from "@/components/ui/icon";
import type { DisplayStatus } from "@/types/status";

type ProductPreviewProps = Readonly<{ status: DisplayStatus }>;

const navItems: Array<{ icon: IconName; label: string; active?: boolean }> = [
  { icon: "layers", label: "Overview", active: true },
  { icon: "command", label: "Projects" },
  { icon: "check", label: "My tasks" },
  { icon: "document", label: "Documents" },
];

const tasks = [
  { title: "Finalize onboarding flow", meta: "Product · Today", tone: "violet" },
  { title: "Review Q4 campaign brief", meta: "Marketing · Tomorrow", tone: "amber" },
  { title: "Map API permissions", meta: "Platform · Nov 20", tone: "mint" },
];

export function ProductPreview({ status }: ProductPreviewProps) {
  return (
    <div className="product-preview reveal reveal--delay-2" aria-label="Illustrative ProjectBridge dashboard">
      <div className="product-preview__glow" aria-hidden="true" />
      <div className="app-window">
        <div className="app-window__bar">
          <div className="window-dots" aria-hidden="true"><i /><i /><i /></div>
          <span>acme.projectbridge.app</span>
          <ServiceStatus status={status} compact />
        </div>
        <div className="app-shell">
          <aside className="app-sidebar">
            <div className="mini-brand" aria-hidden="true"><span>PB</span></div>
            <div className="workspace-switcher">
              <span className="workspace-avatar">A</span>
              <span><small>Workspace</small>Acme Studio</span>
              <Icon name="chevron" />
            </div>
            <nav aria-label="Dashboard preview navigation">
              {navItems.map((item) => (
                <span className={item.active ? "active" : undefined} key={item.label}>
                  <Icon name={item.icon} /> {item.label}
                </span>
              ))}
            </nav>
            <div className="app-sidebar__footer">
              <span className="member-stack" aria-hidden="true"><i>MK</i><i>JR</i><i>+4</i></span>
              <small>6 members online</small>
            </div>
          </aside>
          <div className="app-content">
            <div className="app-content__header">
              <div><small>Tuesday, November 16</small><h2>Good morning, Maya</h2></div>
              <button className="icon-button" aria-label="Search preview"><Icon name="search" /></button>
            </div>
            <div className="metric-row">
              <div><small>Active projects</small><strong>08</strong><span>+2 this month</span></div>
              <div><small>Tasks completed</small><strong>74%</strong><span className="chart-line" aria-hidden="true"><i /><i /><i /><i /><i /></span></div>
              <div><small>Knowledge indexed</small><strong>1.2k</strong><span>Across 46 sources</span></div>
            </div>
            <div className="work-grid">
              <section className="task-panel">
                <div className="panel-heading"><div><small>Focus</small><h3>Next up</h3></div><span>3 tasks</span></div>
                <div className="task-list">
                  {tasks.map((task) => (
                    <div className="task-row" key={task.title}>
                      <i className={`task-check task-check--${task.tone}`} />
                      <span><strong>{task.title}</strong><small>{task.meta}</small></span>
                      <span className="task-owner">{task.title.slice(0, 2).toUpperCase()}</span>
                    </div>
                  ))}
                </div>
              </section>
              <section className="ai-panel">
                <div className="ai-panel__orb"><Icon name="spark" /></div>
                <small>ProjectBridge AI</small>
                <h3>Brief processed</h3>
                <p>6 tasks suggested from <strong>campaign-brief.pdf</strong></p>
                <div className="ai-panel__action"><Icon name="check" /> Ready for review <Icon name="arrow" /></div>
              </section>
            </div>
          </div>
        </div>
      </div>
      <div className="floating-note floating-note--left">
        <Icon name="document" />
        <span><small>Source attached</small>campaign-brief.pdf</span>
        <Icon name="check" />
      </div>
      <div className="floating-note floating-note--right">
        <span className="pulse" />
        <span><small>Assistant connected</small>via MCP</span>
      </div>
    </div>
  );
}

