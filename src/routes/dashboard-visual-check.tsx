import { createFileRoute } from "@tanstack/react-router";
import { Clapperboard, FolderOpen, Layers3, Play, Sparkles, WandSparkles } from "lucide-react";
import { useState } from "react";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { UploadComposer } from "@/components/dashboard/UploadComposer";
import { pageHead } from "@/lib/seo";

export const Route = createFileRoute("/dashboard-visual-check")({
  head: () => pageHead("Dashboard visual check", "Temporary isolated dashboard layout check."),
  component: DashboardVisualCheck,
});

const projects = [
  ["Late-night ranked highlights", "6 clips", "2 hours ago"],
  ["Community watch party", "4 clips", "Yesterday"],
  ["Survival world — episode 42", "Processing", "3 days ago"],
];

function DashboardVisualCheck() {
  const [search, setSearch] = useState("");
  return (
    <DashboardShell displayName="Robens" email="creator@example.com" projectCount={3} search={search} onSearchChange={setSearch}>
      <section id="overview" className="animate-in-up scroll-mt-28">
        <p className="mb-2 flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.18em] text-ember"><span className="h-1.5 w-1.5 rounded-full bg-ember animate-pulse-dot" /> Your creative space</p>
        <h1 className="text-[1.75rem] font-medium leading-tight tracking-[-0.035em] sm:text-4xl">Welcome back, <span className="font-display italic text-ember">Robens.</span></h1>
        <p className="mt-2 text-sm text-muted-foreground sm:text-base">Your next standout moment is already in the footage.</p>
        <div className="mt-7 grid grid-cols-3 gap-2.5 sm:gap-4">
          {[[FolderOpen, "Projects", "3"], [Clapperboard, "Clips found", "10"], [WandSparkles, "Processing", "1"]].map(([Icon, label, value]) => {
            const I = Icon as typeof FolderOpen;
            return <div key={label as string} className="rounded-2xl border border-border bg-card/80 p-3 shadow-soft sm:p-5"><div className="flex items-center justify-between"><p className="text-[11px] text-muted-foreground sm:text-xs">{label as string}</p><I className="hidden h-4 w-4 text-muted-foreground sm:block" /></div><p className="mt-2 font-display text-3xl sm:mt-3 sm:text-4xl">{value as string}</p><p className="mt-2 hidden text-[11px] text-muted-foreground sm:block">In your workspace</p></div>;
          })}
        </div>
      </section>
      <div className="mt-6 grid items-start gap-5 xl:grid-cols-[minmax(0,1.65fr)_minmax(280px,.7fr)]">
        <UploadComposer onUploaded={async () => {}} />
        <aside id="activity" className="rounded-[24px] border border-border bg-card/80 p-5 shadow-pop sm:p-6">
          <div className="flex items-center justify-between"><div><p className="text-sm font-medium">Weekly activity</p><p className="mt-1 text-xs text-muted-foreground">Projects created in the last 7 days</p></div><Layers3 className="h-4 w-4 text-ember" /></div>
          <div className="mt-6 flex h-[104px] items-end justify-between gap-2">{[20, 45, 30, 75, 45, 90, 60].map((height, i) => <div key={i} className="flex h-full flex-1 flex-col items-center justify-end gap-2"><div className="flex h-[72px] w-full max-w-7 items-end rounded-full bg-muted/70"><div className="w-full rounded-full bg-ember" style={{ height: `${height}%` }} /></div><span className="text-[10px] text-muted-foreground">{["M", "T", "W", "T", "F", "S", "S"][i]}</span></div>)}</div>
          <div className="mt-5 rounded-2xl border border-border bg-surface/70 p-4"><p className="flex items-center gap-2 text-xs font-medium"><Sparkles className="h-3.5 w-3.5 text-ember" /> A simpler workflow</p><p className="mt-3 text-xs leading-6 text-muted-foreground">1&nbsp;&nbsp; Upload your recording<br />2&nbsp;&nbsp; Describe the best moments<br />3&nbsp;&nbsp; Review your clips</p></div>
        </aside>
      </div>
      <section id="projects" className="mt-10 scroll-mt-28">
        <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-ember">Your library</p><h2 className="mt-2 text-2xl font-medium tracking-tight">Recent projects</h2><p className="mt-1.5 text-sm text-muted-foreground">Pick up where you left off, or review your newest clips.</p>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">{projects.map(([title, clips, updated], index) => <div key={title} className="overflow-hidden rounded-[20px] border border-border bg-card shadow-soft transition hover:-translate-y-1 hover:shadow-float"><div className="project-visual relative aspect-[16/8.5] border-b border-border"><span className="absolute left-3 top-3 rounded-full border border-border bg-cover-background/70 px-2.5 py-1 text-[10px] text-cover-muted">Upload</span><span className="absolute left-1/2 top-1/2 grid h-12 w-12 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border border-cover-muted/20 bg-cover-background/45 text-cover-foreground shadow-pop"><Play className="ml-0.5 h-4 w-4 fill-current" /></span><div className="absolute inset-x-4 bottom-3 flex h-6 items-end gap-[3px] opacity-60">{Array.from({ length: 28 }).map((_, bar) => <span key={bar} className="flex-1 rounded-full bg-cover-muted" style={{ height: `${20 + Math.abs(Math.sin(bar * 1.35 + index)) * 75}%` }} />)}</div></div><div className="p-4"><h3 className="text-sm font-medium">{title}</h3><div className="mt-3 flex justify-between text-[11px] text-muted-foreground"><span>{clips}</span><span>{updated}</span></div></div></div>)}</div>
      </section>
    </DashboardShell>
  );
}
