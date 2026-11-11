import { Link, useNavigate, useRouteContext, useRouterState } from "@tanstack/react-router";
import {
  Activity,
  Clapperboard,
  FolderOpen,
  LayoutDashboard,
  LogOut,
  Menu,
  PanelLeft,
  PanelLeftClose,
  Plus,
  Search,
  Sparkles,
  Zap,
} from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Brand } from "@/components/Brand";
import { focusComposer } from "@/components/dashboard/focusComposer";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { supabase } from "@/integrations/supabase/client";
import { cn } from "@/lib/utils";

// Placeholder until credit balances are stored per account.
export const CREDITS = { remaining: 120, total: 150 } as const;

const navigation = [
  { id: "/dashboard", label: "New clip", icon: LayoutDashboard },
  { id: "/dashboard/projects", label: "Projects", icon: FolderOpen },
  { id: "/dashboard/activity", label: "Activity", icon: Activity },
] as const;

type DashboardShellProps = {
  children: ReactNode;
  displayName: string;
  email?: string | undefined;
  avatarUrl?: string | null | undefined;
  projectCount: number;
  search?: string;
  onSearchChange?: (value: string) => void;
  demoMode?: boolean;
};

export function DashboardShell({
  children,
  displayName,
  email,
  avatarUrl,
  projectCount,
  search = "",
  onSearchChange,
  demoMode = false,
}: DashboardShellProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const activeSection = useRouterState({
    select: (r) => r.location.pathname.replace(/\/$/, ""),
  }) as (typeof navigation)[number]["id"];
  const searchRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const { queryClient } = useRouteContext({ from: "__root__" });

  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, []);

  const goTo = (id: (typeof navigation)[number]["id"]) => {
    setMobileOpen(false);
    void navigate({ to: id });
  };

  const signOut = async () => {
    await queryClient.cancelQueries();
    queryClient.clear();
    await supabase.auth.signOut();
    await navigate({ to: "/auth", replace: true });
  };

  const startNew = () => {
    setMobileOpen(false);
    if (demoMode) return void navigate({ to: "/auth" });
    if (activeSection === "/dashboard") return focusComposer();
    void navigate({ to: "/dashboard" }).then(() => setTimeout(focusComposer, 50));
  };

  const sidebar = (mobile = false) => (
    <SidebarContent
      collapsed={!mobile && collapsed}
      activeSection={activeSection}
      displayName={displayName}
      email={email}
      avatarUrl={avatarUrl}
      projectCount={projectCount}
      onGoTo={goTo}
      onCreate={startNew}
      onSignOut={() => (demoMode ? void navigate({ to: "/auth" }) : void signOut())}
      demoMode={demoMode}
    />
  );

  return (
    <div className="clipspark-skin dashboard-skin flex min-h-screen w-full overflow-x-hidden bg-background text-foreground">
      <aside
        className={cn(
          "sticky top-0 hidden h-screen shrink-0 flex-col border-r border-border bg-sidebar/80 backdrop-blur-xl transition-[width] duration-300 lg:flex",
          collapsed ? "w-[76px]" : "w-[248px]",
        )}
      >
        <div
          className={cn(
            "flex h-[72px] items-center border-b border-border px-5",
            collapsed ? "justify-center px-0" : "justify-between",
          )}
        >
          {!collapsed && <Brand />}
          <button
            type="button"
            onClick={() => setCollapsed((value) => !value)}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-xl text-muted-foreground transition hover:bg-accent hover:text-foreground"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <PanelLeft className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </button>
        </div>
        {sidebar()}
      </aside>

      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent
          side="left"
          className="clipspark-skin dashboard-skin w-[290px] border-border bg-sidebar p-0 text-foreground"
        >
          <SheetTitle className="sr-only">Workspace navigation</SheetTitle>
          <div className="flex h-[72px] items-center border-b border-border px-5">
            <Brand />
          </div>
          {sidebar(true)}
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-border bg-background/80 backdrop-blur-xl">
          <div className="grid h-[72px] grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 px-3 sm:gap-4 sm:px-6 lg:px-8">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="grid h-10 w-10 place-items-center rounded-xl border border-border bg-card text-muted-foreground shadow-soft transition hover:text-foreground lg:hidden"
              aria-label="Open navigation"
            >
              <Menu className="h-[18px] w-[18px]" />
            </button>
            <div className="hidden items-center gap-2 text-sm text-muted-foreground lg:flex">
              <Clapperboard className="h-4 w-4 text-ember" />
              <span>Creator workspace</span>
            </div>
            {onSearchChange ? (
              <label className="mx-auto flex h-10 w-full max-w-md items-center gap-2.5 rounded-xl border border-border bg-card px-4 shadow-soft transition focus-within:border-ember/40 focus-within:shadow-pop">
                <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
                <input
                  ref={searchRef}
                  value={search}
                  onChange={(event) => onSearchChange(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Escape") {
                      onSearchChange("");
                      event.currentTarget.blur();
                    }
                  }}
                  placeholder="Search projects…"
                  aria-label="Search projects"
                  className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground/70"
                />
                <kbd className="hidden rounded-md border border-border bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground sm:block">
                  ⌘ K
                </kbd>
              </label>
            ) : (
              <div />
            )}
            <div className="flex items-center gap-2">
              <Link
                to="/pricing"
                className="inline-flex h-10 items-center gap-1.5 rounded-xl border border-ember/25 bg-ember/10 px-2.5 text-xs font-medium text-foreground shadow-soft transition hover:border-ember/50 lg:hidden"
                aria-label={`${CREDITS.remaining} credits left`}
              >
                <Zap className="h-3.5 w-3.5 text-ember" />
                {CREDITS.remaining}
              </Link>
              <button
                type="button"
                onClick={startNew}
                className="glow-border glow-border-soft inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-primary px-3 text-sm font-medium text-primary-foreground shadow-pop transition hover:-translate-y-0.5 sm:px-4"
              >
                <Plus className="h-4 w-4" />
                <span className="hidden sm:inline">
                  {demoMode ? "Sign in to create" : "New project"}
                </span>
              </button>
            </div>
          </div>
        </header>
        <main className="relative min-w-0 flex-1 overflow-hidden">
          <div className="ember-orb pointer-events-none absolute -top-40 left-1/3 h-[420px] w-[560px] opacity-40" />
          <div className="relative mx-auto w-full max-w-[1480px] px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

type SidebarContentProps = {
  collapsed: boolean;
  activeSection: (typeof navigation)[number]["id"];
  displayName: string;
  email?: string | undefined;
  avatarUrl?: string | null | undefined;
  projectCount: number;
  onGoTo: (id: (typeof navigation)[number]["id"]) => void;
  onSignOut: () => void;
  onCreate: () => void;
  demoMode?: boolean;
};

function SidebarContent({
  collapsed,
  activeSection,
  displayName,
  email,
  avatarUrl,
  projectCount,
  onGoTo,
  onSignOut,
  onCreate,
  demoMode = false,
}: SidebarContentProps) {
  const initials = displayName.trim().slice(0, 1).toUpperCase() || "N";
  return (
    <div className={cn("flex min-h-0 flex-1 flex-col p-3", collapsed && "items-center px-2")}>
      <button
        type="button"
        onClick={onCreate}
        className={cn(
          "mb-7 mt-3 inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-xl border border-ember/20 bg-ember/10 text-sm font-medium text-foreground shadow-soft transition hover:border-ember/40 hover:bg-ember/15",
          collapsed ? "w-11" : "w-full",
        )}
        title="Create a clip"
      >
        <Sparkles className="h-4 w-4 text-ember" />
        {!collapsed && (demoMode ? "Sign in to create" : "Create a clip")}
      </button>

      <p
        className={cn(
          "mb-2 px-3 text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground",
          collapsed && "sr-only",
        )}
      >
        Workspace
      </p>
      <nav className="flex w-full flex-col gap-1" aria-label="Workspace">
        {navigation.map((item) => (
          <button
            type="button"
            key={item.id}
            onClick={() => onGoTo(item.id)}
            aria-current={activeSection === item.id ? "page" : undefined}
            title={item.label}
            className={cn(
              "group flex h-11 w-full items-center gap-3 rounded-xl px-3 text-sm transition-all duration-200",
              activeSection === item.id
                ? "bg-accent font-medium text-foreground shadow-soft ring-1 ring-border"
                : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
              collapsed && "justify-center px-0",
            )}
          >
            <item.icon
              className={cn(
                "h-[17px] w-[17px] shrink-0",
                activeSection === item.id && "text-ember",
              )}
            />
            {!collapsed && item.label}
            {!collapsed && activeSection === item.id && (
              <span className="ml-auto h-1.5 w-1.5 rounded-full bg-ember shadow-[0_0_10px_var(--ember)]" />
            )}
          </button>
        ))}
      </nav>

      <div className="mt-auto pt-6">
        {!collapsed ? (
          <div className="mb-4 rounded-2xl border border-border bg-card/70 p-4 shadow-soft">
            <div className="flex items-center justify-between gap-3">
              <p className="flex items-center gap-1.5 text-xs font-medium">
                <Zap className="h-3.5 w-3.5 text-ember" /> Credits
              </p>
              <span className="text-[10px] text-muted-foreground">
                {projectCount} {projectCount === 1 ? "project" : "projects"}
              </span>
            </div>
            <p className="mt-3 font-display text-3xl">
              {CREDITS.remaining}
              <span className="ml-1 text-sm text-muted-foreground">/ {CREDITS.total}</span>
            </p>
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-ember shadow-[0_0_10px_var(--ember)]"
                style={{ width: `${(CREDITS.remaining / CREDITS.total) * 100}%` }}
              />
            </div>
            <Link to="/pricing" className="mt-3 inline-block text-xs text-ember hover:underline">
              Top up credits
            </Link>
          </div>
        ) : (
          <Link
            to="/pricing"
            title={`${CREDITS.remaining} credits left`}
            className="mb-3 grid h-10 w-10 place-items-center rounded-xl border border-ember/25 bg-ember/10"
          >
            <Zap className="h-4 w-4 text-ember" />
          </Link>
        )}
        <Link
          to="/"
          title="Back to website"
          className={cn(
            "mb-2 flex h-10 w-full items-center gap-3 rounded-xl px-3 text-sm text-muted-foreground transition hover:bg-accent hover:text-foreground",
            collapsed && "justify-center px-0",
          )}
        >
          <Clapperboard className="h-4 w-4 shrink-0" />
          {!collapsed && "Back to website"}
        </Link>
        <div
          className={cn(
            "flex w-full items-center gap-2 rounded-2xl border border-border bg-card/50 p-2",
            collapsed && "justify-center border-0 bg-transparent",
          )}
        >
          {avatarUrl ? (
            <img
              src={avatarUrl}
              alt=""
              className="h-9 w-9 shrink-0 rounded-full border border-border object-cover"
            />
          ) : (
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full border border-ember/20 bg-ember/10 text-xs font-semibold text-ember">
              {initials}
            </span>
          )}
          {!collapsed && (
            <>
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-medium">{displayName}</p>
                <p className="truncate text-[10px] text-muted-foreground">
                  {demoMode ? "Sample data only" : email || "Creator account"}
                </p>
              </div>
              <button
                type="button"
                onClick={onSignOut}
                className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-muted-foreground transition hover:bg-accent hover:text-foreground"
                aria-label={demoMode ? "Sign in" : "Sign out"}
                title={demoMode ? "Sign in" : "Sign out"}
              >
                <LogOut className="h-3.5 w-3.5" />
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
