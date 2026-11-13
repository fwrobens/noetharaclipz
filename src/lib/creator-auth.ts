import { createMiddleware } from "@tanstack/react-start";

// Creator functions use the same host-only session cookies as the HTTP beta
// gate and legacy editor. No service-role client or browser-provided owner ID.
export const requireCreatorAuth = createMiddleware({ type: "function" }).server(
  async ({ next }) => {
    const { serverSupabase } = await import("./supabase/server");
    const { betaOwnerAllowed } = await import("./beta-access.server");
    const { betaEnabled } = await import("./beta");
    const supabase = serverSupabase();
    const { data, error } = await supabase.auth.getUser();
    if (error || !data.user || (betaEnabled() && !betaOwnerAllowed(data.user))) {
      throw new Error("Sign in with your invited account to open this workspace.");
    }
    return next({ context: { supabase, userId: data.user.id } });
  },
);
