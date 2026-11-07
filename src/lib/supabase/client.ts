import { createBrowserClient } from "@supabase/ssr";
import type { Database } from "@/integrations/supabase/types";
import { supabaseUrl, publishableKey } from "./config";
export const supabase = createBrowserClient<Database>(supabaseUrl, publishableKey, {
  auth: { detectSessionInUrl: false },
});
