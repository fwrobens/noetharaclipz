import { Link, useRouterState } from "@tanstack/react-router";
import { useState, type ReactNode } from "react";
import {
  Home, Library, FolderOpen, LayoutTemplate, Palette, Trash2, Settings, HelpCircle,
  Search, Moon, Sun, Menu, PanelLeftClose, PanelLeft, Scissors, Zap, Plus,
} from "lucide-react";
import { useStore } from "@/lib/store";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

const nav = [
  { to: "/", label: "Home", icon: Home },
  { to: "/library", label: "Library", icon: Library },
  { to: "/projects", label: "Projects", icon: FolderOpen },
  { to: "/templates", label: "Templates", icon: LayoutTemplate },
  { to: "/brand-kit", label: "Brand Kit", icon: Palette },
  { to: "/trash", label: "Recently Deleted", icon: Trash2 },
] as const;

function Logo({ compact }: { compact?: boolean }) {
  return (
    <Link to="/" className="flex items-center gap-2">
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-foreground text-background shadow-pop">
        <Scissors className="h-4 w-4" />
      </span>
      {!compact && <span className="font-display text-lg font-bold tracking-tight">Clipwave</span>}
    </Link>
  );
}

function NavList({ compact, onNavigate }: { compact?: boolean | undefined; onNavigate?: (() => void) | undefined }) {
  const path = useRouterState({ select: (r) => r.location.pathname });
  return (
    <nav className="flex flex-col gap-1">
      {nav.map((n) => {
        const active = n.to === "/" ? path === "/" : path.startsWith(n.to);
        return (
          <Link
            key={n.to}
            to={n.to}
            onClick={onNavigate}
            title={n.label}
            className={cn(
              "flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-all",
              active
                ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium shadow-soft ring-1 ring-border"
                : "text-muted-foreground hover:bg-sidebar-accent/70 hover:text-foreground",
              compact && "justify-center px-0",
            )}
          >
            <n.icon className="h-4 w-4 shrink-0" />
            {!compact && n.label}
          </Link>
        );
      })}
    </nav>
  );
}

function SidebarBody({ compact, onNavigate }: { compact?: boolean | undefined; onNavigate?: (() => void) | undefined }) {
  return (
    <div className="flex h-full flex-col gap-6 p-3">
      <NavList compact={compact} onNavigate={onNavigate} />
      <div className="mt-auto flex flex-col gap-3">
        {!compact && (
          <div className="rounded-2xl border bg-card p-3 shadow-soft">
            <div className="flex items-center gap-2 text-sm font-medium"><Zap className="h-4 w-4 text-warning" /> 120 credits left</div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted"><div className="h-full w-2/3 rounded-full bg-primary" /></div>
            <button className="mt-3 w-full rounded-lg bg-foreground py-1.5 text-xs font-medium text-background shadow-soft transition hover:opacity-90">Upgrade plan</button>
          </div>
        )}
        <div className="flex flex-col gap-1 text-sm text-muted-foreground">
          {[{ i: Settings, l: "Settings" }, { i: HelpCircle, l: "Help" }].map(({ i: I, l }) => (
            <button key={l} title={l} className={cn("flex items-center gap-3 rounded-xl px-3 py-2 hover:bg-sidebar-accent hover:text-foreground", compact && "justify-center px-0")}>
              <I className="h-4 w-4" /> {!compact && l}
            </button>
          ))}
        </div>
        <div className={cn("flex items-center gap-2 rounded-xl p-2", compact && "justify-center")}>
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-accent text-xs font-semibold text-accent-foreground">RB</span>
          {!compact && (
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">Robens</p>
              <p className="truncate text-xs text-muted-foreground">Creator plan</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { dark, toggleDark } = useStore();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen w-full bg-background">
      <aside className={cn("sticky top-0 hidden h-screen shrink-0 flex-col border-r bg-sidebar transition-[width] duration-300 md:flex", collapsed ? "w-16" : "w-60")}>
        <div className={cn("flex h-14 items-center px-4", collapsed ? "justify-center px-0" : "justify-between")}>
          {!collapsed && <Logo />}
          <button onClick={() => setCollapsed((c) => !c)} className="rounded-lg p-1.5 text-muted-foreground hover:bg-sidebar-accent hover:text-foreground" aria-label="Toggle sidebar">
            {collapsed ? <PanelLeft className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </button>
        </div>
        <SidebarBody compact={collapsed} />
      </aside>

      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" className="w-72 bg-sidebar p-0">
          <SheetTitle className="sr-only">Menu</SheetTitle>
          <div className="flex h-14 items-center px-4"><Logo /></div>
          <SidebarBody onNavigate={() => setMobileOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 grid h-14 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 border-b bg-background/80 px-3 backdrop-blur-md sm:gap-4 sm:px-6">
          <div className="flex items-center gap-2 md:hidden">
            <button onClick={() => setMobileOpen(true)} className="rounded-lg p-2 hover:bg-muted" aria-label="Open menu"><Menu className="h-5 w-5" /></button>
            <Logo compact />
          </div>
          <div className="hidden md:block" />
          <label className="mx-auto flex w-full max-w-md items-center gap-2 rounded-xl border bg-card px-3 py-1.5 text-sm shadow-soft focus-within:ring-2 focus-within:ring-ring/40">
            <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
            <input placeholder="Search clips, projects…" className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-muted-foreground" />
            <kbd className="hidden rounded border bg-muted px-1.5 text-[10px] text-muted-foreground sm:block">⌘K</kbd>
          </label>
          <div className="flex items-center gap-1 sm:gap-2">
            <button onClick={toggleDark} className="rounded-xl border bg-card p-2 shadow-soft transition hover:shadow-pop" aria-label="Toggle theme">
              {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            <Link to="/" className="hidden items-center gap-1.5 rounded-xl bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow-pop transition hover:-translate-y-0.5 sm:flex">
              <Plus className="h-4 w-4" /> New
            </Link>
          </div>
        </header>
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}
