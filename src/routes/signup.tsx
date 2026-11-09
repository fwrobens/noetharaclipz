import { createFileRoute } from "@tanstack/react-router";
import { ClipSparkAuth } from "@/components/ClipSparkAuth";
import { pageHead } from "@/lib/seo";
export const Route = createFileRoute("/signup")({ head: () => pageHead("Create account","Join NoetharaClipZ."), component: () => <ClipSparkAuth initialMode="signup" /> });
