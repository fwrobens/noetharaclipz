import { createServerFn } from "@tanstack/react-start";
export const fetchIdentity = createServerFn({ method: "GET" }).handler(async () => {
  const { serverSupabase } = await import("./supabase/server");
  const { data, error } = await serverSupabase().auth.getUser();
  if (
    error &&
    (error.name === "AuthRetryableFetchError" || error.status === 0 || (error.status ?? 0) >= 500)
  )
    throw new Error("Authentication is temporarily unavailable. Please retry.");
  return error ? null : data.user;
});
