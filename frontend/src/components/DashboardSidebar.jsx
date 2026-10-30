import React from 'react';
import { Home, ChartNoAxesCombined, Users, ClipboardList, CalendarDays, FileText, ShieldCheck, Settings2, Search } from 'lucide-react';
import './DashboardShell.css';

const ICONS = {
  home: Home,
  performance: ChartNoAxesCombined,
  team: Users,
  appraisals: ClipboardList,
  meetings: CalendarDays,
  reports: FileText,
  compliance: ShieldCheck,
  accounts: Settings2,
  search: Search,
};

export default function DashboardSidebar({ items, activeId, onSelect }) {
  return <aside className="ts-dashboard-sidebar" aria-label="Dashboard sections">
    {items.map((item) => {
      const Icon = ICONS[item.icon] || Home;
      const active = activeId === item.id;
      return <button key={item.id} type="button" className={`ts-nav-item${active ? ' is-active' : ''}`} aria-current={active ? 'page' : undefined} onClick={() => onSelect(item)}>
        <span className="ts-nav-circle"><Icon size={21} strokeWidth={2.1} aria-hidden="true" /></span>
        <span className="ts-nav-label">{item.label}</span>
      </button>;
    })}
  </aside>;
}
