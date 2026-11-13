import { useQuery } from "@tanstack/react-query";
import { supabase } from "./supabase/client";
const cache = new Map<string, { url: string; expires: number }>();
export const clearMediaCache = () => cache.clear();
const RENDERED_CLIP =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.mp4$/i;

export async function signedMedia(bucket: string, path: string, download?: string) {
  const {
    data: { session },
    error: authError,
  } = await supabase.auth.getSession();
  if (authError || !session) throw new Error("Sign in to download private media.");
  const key = `${session.user.id}/${bucket}/${path}/${download ?? ""}`,
    previous = cache.get(key);
  if (previous && previous.expires > Date.now()) return previous.url;
  const { data, error } = await supabase.storage
    .from(bucket)
    .createSignedUrl(path, 600, download ? { download } : undefined);
  if (error || !data?.signedUrl) throw error ?? new Error("Sign in to download private media.");
  cache.set(key, { url: data.signedUrl, expires: Date.now() + 300000 });
  return data.signedUrl;
}

// Website Download button. Signs the private rendered-clips object for this
// session and lets the browser save it. The signed URL is a short-lived
// capability; it is not a public object URL and is not logged.
export async function downloadRenderedClip(path: string) {
  if (!RENDERED_CLIP.test(path)) throw new Error("Download failed");
  const url = await signedMedia("rendered-clips", path, "noetharaclipz.mp4");
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    throw new Error("Download failed");
  }
  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") throw new Error("Download failed");
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "noetharaclipz.mp4";
  anchor.rel = "noopener noreferrer";
  anchor.referrerPolicy = "no-referrer";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
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
