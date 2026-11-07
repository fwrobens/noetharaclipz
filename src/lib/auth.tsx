import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { User } from "@supabase/supabase-js";
import { useQueryClient } from "@tanstack/react-query";
import { redirect } from "@tanstack/react-router";
import { supabase } from "./supabase/client";
import { fetchIdentity } from "./auth.functions";
const AuthContext = createContext<{ user: User | null; loading: boolean }>({
  user: null,
  loading: true,
});
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const cache = useQueryClient();
  useEffect(() => {
    let active = true;
    supabase.auth.getUser().then(({ data }) => {
      if (active) {
        setUser(data.user);
        setLoading(false);
      }
    });
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      if (active) {
        setUser(session?.user ?? null);
        setLoading(false);
        if (event === "SIGNED_OUT") cache.clear();
      }
    });
    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, [cache]);
  return <AuthContext.Provider value={{ user, loading }}>{children}</AuthContext.Provider>;
}
export const useAuth = () => useContext(AuthContext);
export async function requireAuth() {
  const user = await fetchIdentity();
  if (!user) throw redirect({ to: "/login" });
  return { user };
}
