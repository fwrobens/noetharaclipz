import { queryOptions } from "@tanstack/react-query";
import { loadCreator } from "./creator.functions";
export const creatorQuery = () => queryOptions({ queryKey: ["creator"], queryFn: () => loadCreator(), staleTime: 15_000 });