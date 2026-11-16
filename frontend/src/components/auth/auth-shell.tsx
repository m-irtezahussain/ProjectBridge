import type { ReactNode } from "react";
import Link from "next/link";

import { Brand } from "@/components/landing/brand";
import { Icon } from "@/components/ui/icon";

type AuthShellProps = Readonly<{
  children: ReactNode;
  eyebrow: string;
  title: string;
  description: string;
}>;

export function AuthShell({ children, eyebrow, title, description }: AuthShellProps) {
  return (
    <main className="auth-page">
      <div className="auth-page__ambient" aria-hidden="true"><i /><i /><i /></div>
      <header className="auth-header">
        <Brand />
        <Link className="auth-header__back" href="/">
          Back to home <Icon name="arrow" />
        </Link>
      </header>
      <div className="auth-layout">
        <section className="auth-form-panel" aria-labelledby="auth-title">
          <div className="auth-form-panel__inner">
            <span className="eyebrow auth-enter">{eyebrow}</span>
            <h1 id="auth-title" className="auth-enter auth-enter--1">{title}</h1>
            <p className="auth-form-panel__intro auth-enter auth-enter--2">{description}</p>
            <div className="auth-enter auth-enter--3">{children}</div>
          </div>
        </section>
        <aside className="auth-story" aria-label="ProjectBridge product preview">
          <div className="auth-story__copy">
            <blockquote>“Keep the source. Keep the context. Move the work.”</blockquote>
            <p>One permission-aware workspace for your team and every assistant they trust.</p>
          </div>
          <div className="auth-visual" aria-hidden="true">
            <div className="auth-visual__bar"><span>Project launch</span><i>Live</i></div>
            <div className="auth-visual__body">
              <div className="auth-visual__metric"><small>Progress</small><strong>74%</strong><span><i /></span></div>
              <div className="auth-visual__activity">
                <small>Recent activity</small>
                <p><b>AI</b><span><strong>6 tasks created</strong>from campaign-brief.pdf</span><Icon name="check" /></p>
                <p><b>MK</b><span><strong>Timeline updated</strong>Launch moved to Nov 28</span><Icon name="arrow" /></p>
              </div>
            </div>
          </div>
          <div className="auth-story__foot"><Icon name="lock" /> Tenant-isolated by design</div>
        </aside>
      </div>
    </main>
  );
}

