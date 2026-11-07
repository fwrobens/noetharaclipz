import { Link } from "@tanstack/react-router";
import { Film, Loader2, CheckCircle2, MoreHorizontal } from "lucide-react";
import { fmt, type Project } from "@/lib/mock";
import { cn } from "@/lib/utils";

export function VideoCard({ p, className }: { p: Project; className?: string }) {
  return (
    <Link
      to="/project/$id"
      params={{ id: p.id }}
      className={cn("group block overflow-hidden rounded-2xl border bg-card lift", className)}
    >
      <div className="relative aspect-video overflow-hidden">
        <img src={p.thumb} alt="" loading="lazy" width={1088} height={608} className="h-full w-full object-cover transition duration-500 group-hover:scale-105" />
        <span className="absolute left-2 top-2 rounded-md bg-card/90 px-1.5 py-0.5 text-[11px] font-medium shadow-soft backdrop-blur">{p.platform}</span>
        <span className="absolute bottom-2 right-2 rounded-md bg-foreground/80 px-1.5 py-0.5 font-mono text-[11px] text-background">{fmt(p.length)}</span>
      </div>
      <div className="p-3">
        <div className="flex items-start justify-between gap-2">
          <p className="line-clamp-1 text-sm font-medium">{p.title}</p>
          <MoreHorizontal className="h-4 w-4 shrink-0 text-muted-foreground" />
        </div>
        <div className="mt-2 flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <span className="flex items-center gap-1"><Film className="h-3.5 w-3.5" /> {p.highlights.length} clips</span>
          {p.status === "ready" ? (
            <span className="flex items-center gap-1 text-success"><CheckCircle2 className="h-3.5 w-3.5" /> Ready</span>
          ) : (
            <span className="flex items-center gap-1 text-primary"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Processing</span>
          )}
        </div>
        <p className="mt-1 text-[11px] text-muted-foreground">Edited {p.edited}</p>
      </div>
    </Link>
  );
}
