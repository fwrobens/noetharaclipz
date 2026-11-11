import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import type { User } from "@supabase/supabase-js";
import { useQueryClient } from "@tanstack/react-query";
import { redirect } from "@tanstack/react-router";
import { supabase } from "./supabase/client";
import { fetchIdentity } from "./auth.functions";
import { clearMediaCache } from "./media";
const AuthContext = createContext<{ user: User | null; loading: boolean }>({
  user: null,
  loading: true,
});
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const cache = useQueryClient();
  const subject = useRef<string | null>(null);
  useEffect(() => {
    let active = true;
    supabase.auth.getUser().then(({ data }) => {
      if (active) {
        subject.current = data.user?.id ?? null;
        setUser(data.user);
        setLoading(false);
      }
    });
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      if (active) {
        const nextSubject = session?.user.id ?? null;
        if (event === "SIGNED_OUT" || subject.current !== nextSubject) {
          cache.clear();
          clearMediaCache();
        }
        subject.current = nextSubject;
        setUser(session?.user ?? null);
        setLoading(false);
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
