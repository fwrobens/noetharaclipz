import { queryOptions } from "@tanstack/react-query";
import { loadCreator } from "./creator.functions";
import { activeJob } from "./editor";
export const creatorQuery = () =>
  queryOptions({
    queryKey: ["creator"],
    queryFn: () => loadCreator(),
    staleTime: 15_000,
    refetchInterval: (query) =>
      query.state.data?.projects.some((project) =>
        (project.processing_jobs ?? []).some((job) => activeJob(job.status)),
      )
        ? 2500
        : false,
  });
