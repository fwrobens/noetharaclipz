import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "./auth";
import { must } from "./store";
import { supabase } from "./supabase/client";
import type { Json } from "@/integrations/supabase/types";
import type { ClipEdit } from "./editor";
export type Brand = {
  caption_color: string;
  font: ClipEdit["font"];
  ratio: ClipEdit["ratio"];
  caption_style: ClipEdit["caption_style"];
};
const defaults: Brand = {
  caption_color: "#FFFFFF",
  font: "Instrument Sans",
  ratio: "9:16",
  caption_style: "Bold pop",
};
export function useBrand() {
  const { user } = useAuth();
  const cache = useQueryClient();
  const q = useQuery({
    queryKey: ["brand", user?.id],
    enabled: !!user,
    queryFn: async () => {
      const { data, error } = await supabase
        .from("brand_settings")
        .select("settings")
        .eq("owner_id", user!.id)
        .maybeSingle();
      if (error) throw error;
      return { ...defaults, ...((data?.settings as Partial<Brand>) ?? {}) };
    },
  });
  return {
    ...q,
    brand: q.data ?? defaults,
    save: async (change: Partial<Brand>) => {
      if (!user) throw new Error("Sign in first");
      must(
        await supabase
          .from("brand_settings")
          .upsert({ owner_id: user.id, settings: { ...(q.data ?? defaults), ...change } as Json })
          .select()
          .single(),
      );
      await cache.invalidateQueries({ queryKey: ["brand", user.id] });
    },
  };
}
