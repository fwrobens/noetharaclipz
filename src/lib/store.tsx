import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { seedProjects, thumbs, type Project, type Highlight } from "./mock";

export interface ChatMsg {
  id: string;
  role: "user" | "ai";
  text: string;
  clipIds?: string[] | undefined;
}

interface Store {
  projects: Project[];
  chats: Record<string, ChatMsg[]>;
  dark: boolean;
  toggleDark: () => void;
  createProject: (prompt: string) => string;
  addHighlights: (pid: string, h: Highlight[]) => void;
  setDeleted: (pid: string, deleted: boolean) => void;
  pushMsg: (pid: string, m: ChatMsg) => void;
  updateMsg: (pid: string, id: string, text: string, clipIds?: string[]) => void;
}

const Ctx = createContext<Store | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<Project[]>(seedProjects);
  const [chats, setChats] = useState<Record<string, ChatMsg[]>>({});
  const [dark, setDark] = useState(true);

  useEffect(() => {
    setDark(localStorage.getItem("clipwave-dark") !== "0");
  }, []);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("clipwave-dark", dark ? "1" : "0");
  }, [dark]);

  const store: Store = {
    projects,
    chats,
    dark,
    toggleDark: () => setDark((d) => !d),
    createProject: (prompt) => {
      const id = `p${Date.now()}`;
      const isLink = /https?:\/\//.test(prompt);
      setProjects((ps) => [
        {
          id,
          title: isLink ? "Imported stream VOD" : prompt.slice(0, 48) || "Untitled project",
          thumb: thumbs[ps.length % thumbs.length] ?? "",
          platform: /twitch/i.test(prompt) ? "Twitch" : isLink ? "YouTube" : "Upload",
          length: 6480,
          status: "processing",
          edited: "Just now",
          folder: "TikTok",
          highlights: [],
        },
        ...ps,
      ]);
      setChats((c) => ({ ...c, [id]: [{ id: `m${Date.now()}`, role: "user", text: prompt }] }));
      return id;
    },
    addHighlights: (pid, h) =>
      setProjects((ps) => ps.map((p) => (p.id === pid ? { ...p, status: "ready", highlights: [...p.highlights, ...h] } : p))),
    setDeleted: (pid, deleted) => setProjects((ps) => ps.map((p) => (p.id === pid ? { ...p, deleted } : p))),
    pushMsg: (pid, m) => setChats((c) => ({ ...c, [pid]: [...(c[pid] ?? []), m] })),
    updateMsg: (pid, id, text, clipIds) =>
      setChats((c) => ({ ...c, [pid]: (c[pid] ?? []).map((m) => (m.id === id ? { ...m, text, clipIds: clipIds ?? m.clipIds } : m)) })),
  };

  return <Ctx.Provider value={store}>{children}</Ctx.Provider>;
}

export const useStore = () => {
  const s = useContext(Ctx);
  if (!s) throw new Error("StoreProvider missing");
  return s;
};

/** Simulates a streamed AI reply word by word. */
export function streamText(full: string, onChunk: (t: string) => void, done?: () => void) {
  const words = full.split(" ");
  let i = 0;
  const iv = setInterval(() => {
    i++;
    onChunk(words.slice(0, i).join(" "));
    if (i >= words.length) {
      clearInterval(iv);
      done?.();
    }
  }, 45);
  return () => clearInterval(iv);
}
