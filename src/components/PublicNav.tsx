import { Link, useNavigate, useRouteContext } from "@tanstack/react-router";
import { Menu, ArrowUpRight, LogOut } from "lucide-react";
import { useState } from "react";
import { Brand } from "./Brand";
import { Button } from "./ui/button";
import { useSessionUser } from "@/lib/session";
import { supabase } from "@/integrations/supabase/client";
export function PublicNav() {
  const [open, setOpen] = useState(false);
  const user = useSessionUser();
  const navigate = useNavigate();
  const { queryClient } = useRouteContext({ from: "__root__" });
  const signOut = async () => { await queryClient.cancelQueries(); queryClient.clear(); await supabase.auth.signOut(); await navigate({ to: "/auth", replace: true }); };
  return <header className="sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur-xl"><div className="mx-auto grid h-20 max-w-7xl grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-5 sm:px-8 md:grid-cols-[1fr_auto_1fr]">
    <Brand /><nav className="hidden items-center gap-8 text-sm text-muted-foreground md:flex"><Link to="/" hash="features">Features</Link><Link to="/pricing" activeProps={{ className: "text-foreground" }}>Pricing</Link><Link to="/dashboard">Workspace</Link></nav>
    <div className="flex shrink-0 items-center justify-end gap-3"><Button variant="ghost" asChild className="hidden sm:inline-flex"><Link to={user ? "/dashboard" : "/auth"}>{user ? "My workspace" : "Sign in"}</Link></Button><Button asChild className="hidden sm:inline-flex"><Link to={user ? "/dashboard" : "/auth"}>{user ? "Open dashboard" : "Start creating"}<ArrowUpRight /></Link></Button>{user && <Button variant="ghost" size="icon" aria-label="Sign out" title="Sign out" onClick={signOut}><LogOut /></Button>}<Button variant="ghost" size="icon" className="md:hidden" aria-label="Open navigation" onClick={() => setOpen(!open)}><Menu /></Button></div>
    </div>{open && <nav className="flex flex-col gap-4 border-t border-border p-5 text-sm md:hidden"><Link to="/" hash="features" onClick={() => setOpen(false)}>Features</Link><Link to="/pricing" onClick={() => setOpen(false)}>Pricing</Link><Link to="/dashboard" onClick={() => setOpen(false)}>Workspace</Link><Link to="/auth" onClick={() => setOpen(false)}>{user ? "Account" : "Sign in"}</Link></nav>}</header>;
}