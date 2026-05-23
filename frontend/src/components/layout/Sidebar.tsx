import {
  Activity,
  BarChart3,
  Brain,
  Clock,
  Gauge,
  History,
  LayoutDashboard,
  Settings,
  ShieldAlert,
} from "lucide-react";
import { cn } from "@/lib/utils";

export type PageKey =
  | "dashboard"
  | "market"
  | "signal"
  | "backtest"
  | "risk"
  | "model"
  | "history"
  | "settings";

interface SidebarProps {
  activePage: PageKey;
  onNavigate: (page: PageKey) => void;
}

const navItems = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "market", label: "Market", icon: BarChart3 },
  { key: "signal", label: "Signal", icon: Activity },
  { key: "backtest", label: "Backtest", icon: Gauge },
  { key: "risk", label: "Risk", icon: ShieldAlert },
  { key: "model", label: "Model", icon: Brain },
  { key: "history", label: "History", icon: History },
  { key: "settings", label: "Settings", icon: Settings },
] as const;

export function Sidebar({ activePage, onNavigate }: SidebarProps) {
  return (
    <aside className="hidden w-72 shrink-0 border-r border-border bg-white lg:block">
      <div className="border-b border-border p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-sm font-bold text-white">
            LQ
          </div>
          <div>
            <h1 className="text-lg font-semibold">LocalQuant Brain</h1>
            <p className="text-xs text-muted-foreground">Reasoning, confluence, and research</p>
          </div>
        </div>
      </div>
      <nav className="space-y-1 p-3">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = activePage === item.key;
          return (
            <button
              key={item.key}
              onClick={() => onNavigate(item.key)}
              className={cn(
                "flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition",
                active
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </button>
          );
        })}
      </nav>
      <div className="mt-4 px-5 text-xs text-muted-foreground">
        <Clock className="mb-2 h-4 w-4" />
        Signals are decision support, not execution.
      </div>
    </aside>
  );
}
