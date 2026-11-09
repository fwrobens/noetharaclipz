import { createFileRoute } from "@tanstack/react-router";
import { ClipSparkAuth } from "@/components/ClipSparkAuth";
import { pageHead } from "@/lib/seo";
export const Route = createFileRoute("/auth")({ head: () => pageHead("Sign in","Log in or create your NoetharaClipZ account."), component: () => <ClipSparkAuth initialMode="signin" /> });
