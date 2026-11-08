import { Link } from "@tanstack/react-router";
import logo from "@/assets/noethara-logo.png.asset.json";
import { cn } from "@/lib/utils";

export function Brand({ compact = false, className }: { compact?: boolean; className?: string }) {
  return <Link to="/" className={cn("flex min-w-0 items-center gap-2.5", className)}>
    <img src={logo.url} alt="" width={40} height={40} className="h-9 w-9 shrink-0 object-contain" />
    {!compact && <span className="font-display text-base font-semibold">Noethara <span className="text-muted-foreground">Clipz</span></span>}
  </Link>;
}