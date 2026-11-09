import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import hero from "@/assets/creator-studio.jpg";
import { Button, Logo } from "@/components/site";
import { BorderBeam } from "@/components/ui/border-beam";

export function AuthShell({ title, subtitle, children, footer, onOAuth, oauthBusy }: { title: string; subtitle: string; children: ReactNode; footer: ReactNode; onOAuth?: (provider: "google" | "twitch") => void; oauthBusy?: boolean }) {
  return (
    <div className="clipspark-skin grid min-h-screen lg:grid-cols-2">
      <div className="relative flex flex-col px-5 py-8 sm:px-10">
        <div className="grid-bg absolute inset-0 -z-10" />
        <Logo />
        <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-12">
          <div className="animate-in-up">
            <h1 className="text-3xl font-medium tracking-tight">{title}</h1>
            <p className="mt-2 text-sm text-muted-foreground">{subtitle}</p>
            <div className="mt-8 grid grid-cols-2 gap-3">
              <Button variant="ghost" type="button" disabled={oauthBusy} onClick={() => onOAuth?.("google")}>Google</Button>
              <Button variant="ghost" type="button" disabled={oauthBusy} onClick={() => onOAuth?.("twitch")}>Twitch</Button>
            </div>
            <div className="my-6 flex items-center gap-3 text-xs text-muted-foreground">
              <span className="h-px flex-1 bg-border" />or<span className="h-px flex-1 bg-border" />
            </div>
            {children}
            <p className="mt-6 text-center text-sm text-muted-foreground">{footer}</p>
          </div>
        </div>
      </div>
      <div className="relative hidden overflow-hidden border-l border-border bg-surface lg:block">
        <img src={hero} alt="" width={1280} height={1024} className="absolute inset-0 h-full w-full object-cover opacity-80" />
        <div className="absolute inset-0 bg-linear-to-t from-background via-background/30 to-transparent" />
        <div className="absolute bottom-12 left-12 right-12">
          <p className="font-display text-4xl italic leading-tight">Your best moments deserve the spotlight.</p><p className="mt-4 text-sm text-muted-foreground">NoetharaClipZ · AI clipping studio</p>
        </div>
      </div>
    </div>
  );
}

export function Field({ label, ...p }: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <div className="relative overflow-hidden rounded-xl">
        <input {...p} className="h-11 w-full rounded-xl border border-input bg-surface px-4 text-sm outline-none transition focus:border-ember/60 focus:ring-2 focus:ring-ember/20" />
        <BorderBeam size={50} duration={7} radius={12} />
      </div>
    </label>
  );
}

export { Link };