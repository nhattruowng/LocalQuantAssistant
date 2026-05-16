import type { ReactNode } from "react";
import { Sidebar, type PageKey } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";

interface AppShellProps {
  activePage: PageKey;
  onNavigate: (page: PageKey) => void;
  onRefresh: () => void;
  children: ReactNode;
}

export function AppShell({ activePage, onNavigate, onRefresh, children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-background lg:flex">
      <Sidebar activePage={activePage} onNavigate={onNavigate} />
      <div className="min-w-0 flex-1">
        <TopBar onRefresh={onRefresh} />
        <main className="p-4 lg:p-6">{children}</main>
      </div>
    </div>
  );
}
