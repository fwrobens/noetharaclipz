import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { creatorQuery } from "@/lib/creator-query";
import { useSessionUser } from "@/lib/session";

export function useWorkspace() {
  const { data } = useSuspenseQuery(creatorQuery());
  const user = useSessionUser();
  const queryClient = useQueryClient();
  const projects = useMemo(
    () => (data.projects ?? []).filter((project) => project && !project.deleted_at),
    [data.projects],
  );
  const displayName: string =
    data.profile?.display_name?.trim() ||
    user?.user_metadata?.["full_name"] ||
    user?.email?.split("@")[0] ||
    "Creator";
  return {
    data,
    projects,
    displayName,
    firstName: displayName.split(" ")[0] || "Creator",
    shellProps: {
      displayName,
      email: user?.email,
      avatarUrl: data.profile?.avatar_url,
      projectCount: projects.length,
    },
    refresh: () => queryClient.invalidateQueries({ queryKey: ["creator"] }),
  };
}
