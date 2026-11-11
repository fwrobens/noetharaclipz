import { createServerClient } from "@supabase/ssr";
import { getCookies, getRequest, setCookie, setResponseHeader } from "@tanstack/react-start/server";
import type { Database } from "@/integrations/supabase/types";
import { supabaseUrl, publishableKey } from "./config";
export function serverSupabase() {
  setResponseHeader("Cache-Control", "private, no-store");
  return createServerClient<Database>(supabaseUrl, publishableKey, {
    cookieOptions: {
      path: "/",
      sameSite: "lax",
      secure: new URL(getRequest().url).protocol === "https:",
    },
    cookies: {
      getAll: () => Object.entries(getCookies()).map(([name, value]) => ({ name, value })),
      setAll: (cookies) =>
        cookies.forEach(({ name, value, options }) => setCookie(name, value, options)),
    },
  });
}
