import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import type { Json, Tables } from "@/integrations/supabase/types";
import type { Category, ChatMsg, Project } from "./domain";
import { supabase } from "./supabase/client";
import { useAuth } from "./auth";
import { signedMedia } from "./media";
import { editSchema, type ClipEdit } from "./editor";
export type { ChatMsg } from "./domain";
export function must<T>({
  data,
  error,
}: {
  data: T;
  error: { message: string } | null;
}): NonNullable<T> {
  if (error) throw new Error(error.message);
  if (data === null) throw new Error("No data returned");
  return data!;
}
function useData() {
  const { user, loading: authLoading } = useAuth();
  const cache = useQueryClient();
  const uid = user?.id;
  const projects = useQuery({
    queryKey: ["projects", uid],
    enabled: !!uid,
    queryFn: async () => {
      const rows = must(
        await supabase
          .from("projects")
          .select("*, videos(*), highlights(*)")
          .order("created_at", { ascending: false }),
      );
      return Promise.all(
        rows.map(async (p) => {
          const video = p.videos ?? undefined;
          return {
            id: p.id,
            title: p.title,
            thumb: video?.thumbnail_path
              ? await signedMedia("thumbnails", video.thumbnail_path).catch(
                  () => "/media-placeholder.svg",
                )
              : "/media-placeholder.svg",
            platform: p.source_platform,
            length: video?.duration ?? 0,
            status: p.status,
            edited: formatDistanceToNow(new Date(p.updated_at), { addSuffix: true }),
            folder: p.folder,
            deleted: !!p.deleted_at,
            video,
            highlights: p.highlights.map((h) => ({
              id: h.id,
              title: h.title,
              start: h.start_time,
              duration: h.end_time - h.start_time,
              score: h.score,
              category: h.category as Category,
              explanation: h.explanation,
            })),
          } satisfies Project;
        }),
      );
    },
    refetchInterval: 5000,
  });
  const jobs = useQuery({
    queryKey: ["jobs", uid],
    enabled: !!uid,
    queryFn: async () =>
      must(
        await supabase
          .from("processing_jobs")
          .select("*")
          .order("created_at", { ascending: false }),
      ),
    refetchInterval: 4000,
  });
  const messages = useQuery({
    queryKey: ["messages", uid],
    enabled: !!uid,
    queryFn: async () =>
      must(await supabase.from("conversation_messages").select("*").order("created_at")),
    refetchInterval: 5000,
  });
  const clips = useQuery({
    queryKey: ["clips", uid],
    enabled: !!uid,
    queryFn: async () => must(await supabase.from("clips").select("*")),
    refetchInterval: 5000,
  });
  useEffect(() => {
    if (!uid) return;
    const channel = supabase.channel("project-updates-" + uid);
    for (const table of [
      "projects",
      "processing_jobs",
      "highlights",
      "clips",
      "conversation_messages",
    ])
      channel.on(
        "postgres_changes",
        { event: "*", schema: "public", table },
        () =>
          void cache.invalidateQueries({
            predicate: (q) =>
              ["projects", "jobs", "clips", "messages", "artifacts"].includes(
                String(q.queryKey[0]),
              ),
          }),
      );
    channel.subscribe();
    return () => {
      void supabase.removeChannel(channel);
    };
  }, [uid, cache]);
  const chats: Record<string, ChatMsg[]> = {};
  for (const m of messages.data ?? [])
    (chats[m.project_id] ??= []).push({
      id: m.id,
      role: m.role === "assistant" ? "ai" : (m.role as "user" | "system"),
      text: m.content,
      clipIds: m.highlight_ids,
    });
  return {
    projects: uid ? (projects.data ?? []) : [],
    jobs: uid ? (jobs.data ?? []) : [],
    clips: uid ? (clips.data ?? []) : [],
    chats: uid ? chats : {},
    loading: authLoading || (!!uid && (projects.isPending || clips.isPending)),
    error: projects.error ?? jobs.error ?? messages.error ?? clips.error,
  };
}
function useValue() {
  const data = useData();
  const cache = useQueryClient();
  const [dark, setDark] = useState(false);
  useEffect(() => {
    setDark(localStorage.getItem("clipwave-dark") === "1");
  }, []);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("clipwave-dark", dark ? "1" : "0");
  }, [dark]);
  const refresh = () => cache.invalidateQueries();
  return {
    ...data,
    dark,
    toggleDark: () => setDark((d) => !d),
    refresh,
    setDeleted: async (pid: string, deleted: boolean) => {
      const { error } = await supabase.rpc("set_deleted", { pid, deleted });
      if (error) throw error;
      await refresh();
    },
    saveClip: async (hid: string, edit: ClipEdit, expectedRevision?: number) => {
      const valid = editSchema.parse(edit);
      const id = must(
        await supabase.rpc("save_clip", {
          hid,
          edit: valid as Json,
          ...(expectedRevision === undefined ? {} : { expected_revision: expectedRevision }),
        }),
      );
      await refresh();
      return id;
    },
    exportClip: async (clip: Tables<"clips">) => {
      const id = must(
        await supabase.rpc("export_clip", { cid: clip.id, expected_revision: clip.revision }),
      );
      await refresh();
      return id;
    },
    retryJob: async (jid: string) => {
      must(await supabase.rpc("retry_job", { jid }));
      await refresh();
    },
    cancelJob: async (jid: string) => {
      const { error } = await supabase.rpc("cancel_job", { jid });
      if (error) throw error;
      await refresh();
    },
  };
}
type Store = ReturnType<typeof useValue>;
const Context = createContext<Store | null>(null);
export function StoreProvider({ children }: { children: ReactNode }) {
  const store = useValue();
  return <Context.Provider value={store}>{children}</Context.Provider>;
}
export const useStore = () => {
  const value = useContext(Context);
  if (!value) throw new Error("StoreProvider missing");
  return value;
};
export function useArtifacts(pid: string) {
  return useQuery({
    queryKey: ["artifacts", pid],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("analysis_artifacts")
        .select("*")
        .eq("project_id", pid)
        .maybeSingle();
      if (error) throw error;
      return data;
    },
    enabled: !!pid,
    refetchInterval: 10000,
    retry: false,
  });
}
