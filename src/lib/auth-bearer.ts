import { createMiddleware } from "@tanstack/react-start";
import { supabase } from "@/lib/supabase/client";
export const attachCreatorAuth = createMiddleware({ type: "function" }).client(async ({ next }) => {
  const { data } = await supabase.auth.getSession();
  return next({
    headers: data.session ? { Authorization: `Bearer ${data.session.access_token}` } : {},
  });
});
