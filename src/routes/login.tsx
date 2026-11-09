import { createFileRoute } from "@tanstack/react-router";
import { ClipSparkAuth } from "@/components/ClipSparkAuth";
import { pageHead } from "@/lib/seo";
export const Route = createFileRoute("/login")({ head: () => pageHead("Log in","Sign in to your NoetharaClipZ workspace."), component: () => <ClipSparkAuth initialMode="signin" /> });
