"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { LogoutButton } from "@/components/auth/logout-button";
import { Brand } from "@/components/landing/brand";
import { Icon } from "@/components/ui/icon";
import { dashboardNav, dashboardUtilityNav } from "@/data/dashboard";

type DashboardFrameProps = Readonly<{
  children: ReactNode;
  userName: string;
  userEmail: string;
}>;

function initialsFor(name: string): string {
  return name.split(" ").filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
}

export function DashboardFrame({ children, userName, userEmail }: DashboardFrameProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();

  return (
    <div className={`dashboard-app${sidebarOpen ? " sidebar-open" : ""}`}>
      <button className="dashboard-scrim" type="button" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />
      <aside className="dashboard-sidebar" id="dashboard-navigation">
        <div className="dashboard-sidebar__brand"><Brand /></div>
        <button className="workspace-switcher" type="button" title="Workspace switching will be available soon">
          <span>PB</span><span><strong>ProjectBridge</strong><small>Demo workspace</small></span><Icon name="chevron" />
        </button>
        <nav className="dashboard-nav" aria-label="Workspace navigation">
          <small>Workspace</small>
          {dashboardNav.map((item) => (
            <Link
              className={item.href === pathname ? "active" : ""}
              href={item.href}
              key={item.label}
              onClick={() => setSidebarOpen(false)}
            >
              <Icon name={item.icon} /><span>{item.label}</span>{item.count && <b>{item.count}</b>}
            </Link>
          ))}
        </nav>
        <nav className="dashboard-nav dashboard-nav--utility" aria-label="Account navigation">
          <small>Manage</small>
          {dashboardUtilityNav.map((item) => (
            <Link href={item.href} key={item.label} onClick={() => setSidebarOpen(false)}>
              <Icon name={item.icon} /><span>{item.label}</span>
            </Link>
          ))}
        </nav>
        <div className="sidebar-profile">
          <span>{initialsFor(userName)}</span>
          <div><strong>{userName}</strong><small>{userEmail}</small></div>
          <LogoutButton />
        </div>
      </aside>
      <div className="dashboard-main">
        <header className="dashboard-topbar">
          <button
            className="dashboard-menu"
            type="button"
            aria-controls="dashboard-navigation"
            aria-expanded={sidebarOpen}
            aria-label="Open navigation"
            onClick={() => setSidebarOpen(true)}
          ><i /><i /><i /></button>
          <label className="dashboard-search"><Icon name="search" /><input type="search" placeholder="Search projects, tasks, documents…" aria-label="Search workspace" /><kbd>⌘ K</kbd></label>
          <div className="dashboard-topbar__actions">
            <button className="dashboard-notification" type="button" aria-label="Notifications" title="No new notifications"><Icon name="document" /><i /></button>
            <button className="dashboard-create" type="button" title="Project creation will be connected next"><span>+</span> New project</button>
          </div>
        </header>
        {children}
      </div>
    </div>
  );
}
