import { Link } from "@tanstack/react-router";
import { Clapperboard } from "lucide-react";

export function PageHeader({ title, sub }: { title: string; sub: string }) {
  return (
    <div className="mb-6">
      <h1 className="text-2xl font-bold sm:text-3xl">{title}</h1>
      <p className="mt-1 text-sm text-muted-foreground">{sub}</p>
    </div>
  );
}

export function EmptyState({ title, sub }: { title: string; sub: string }) {
  return (
    <div className="mx-auto flex max-w-sm flex-col items-center rounded-3xl border border-dashed bg-card/60 p-10 text-center shadow-soft">
      <span className="grid h-14 w-14 place-items-center rounded-2xl bg-accent text-accent-foreground shadow-pop">
        <Clapperboard className="h-6 w-6" />
      </span>
      <p className="mt-4 font-display text-lg font-semibold">{title}</p>
      <p className="mt-1 text-sm text-muted-foreground">{sub}</p>
      <Link
        to="/"
        className="mt-5 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-pop"
      >
        Start clipping
      </Link>
    </div>
  );
}
