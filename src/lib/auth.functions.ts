import { createServerFn } from "@tanstack/react-start";
export const fetchIdentity = createServerFn({ method: "GET" }).handler(async () => {
  const { serverSupabase } = await import("./supabase/server");
  const { data, error } = await serverSupabase().auth.getUser();
  return error ? null : data.user;
});
