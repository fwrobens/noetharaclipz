import { createServerFn } from "@tanstack/react-start";
export const fetchIdentity = createServerFn({ method: "GET" }).handler(async () => {
  const { serverSupabase } = await import("./supabase/server");
  const { data, error } = await serverSupabase().auth.getUser();
  if (
    error &&
    (error.name === "AuthRetryableFetchError" || error.status === 0 || (error.status ?? 0) >= 500)
  )
    throw new Error("Authentication is temporarily unavailable. Please retry.");
  if (error) return null;
  const { betaEnabled } = await import("./beta");
  const { betaOwnerAllowed } = await import("./beta-access.server");
  return betaEnabled() && !betaOwnerAllowed(data.user) ? null : data.user;
});
