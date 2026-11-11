import { useQuery } from "@tanstack/react-query";
import { supabase } from "./supabase/client";
const cache = new Map<string, { url: string; expires: number }>();
export const clearMediaCache = () => cache.clear();
export async function signedMedia(bucket: string, path: string) {
  const {
    data: { session },
    error: authError,
  } = await supabase.auth.getSession();
  if (authError || !session) throw new Error("Sign in to download private media.");
  const key = `${session.user.id}/${bucket}/${path}`,
    previous = cache.get(key);
  if (previous && previous.expires > Date.now()) return previous.url;
  const { data, error } = await supabase.storage.from(bucket).createSignedUrl(path, 600);
  if (error) throw error;
  cache.set(key, { url: data.signedUrl, expires: Date.now() + 300000 });
  return data.signedUrl;
}
export function useMediaUrl(bucket: string, path: string | undefined | null) {
  return useQuery({
    queryKey: ["media", bucket, path],
    queryFn: () => signedMedia(bucket, path!),
    enabled: !!path,
    staleTime: 240000,
    refetchInterval: 240000,
    retry: 1,
  });
}
