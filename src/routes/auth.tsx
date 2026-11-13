import { createFileRoute, Outlet, useRouterState } from "@tanstack/react-router";
import { ClipSparkAuth } from "@/components/ClipSparkAuth";
import { pageHead } from "@/lib/seo";
export const Route = createFileRoute("/auth")({
  head: () => pageHead("Sign in", "Log in or create your NoetharaClipZ account."),
  component: AuthEntry,
});

function AuthEntry() {
  const path = useRouterState({ select: (state) => state.location.pathname });
  // /auth/callback is nested under this new main route. Its PKCE completion
  // must render instead of being hidden behind the parent sign-in form.
  return path.replace(/\/$/, "") === "/auth" ? <ClipSparkAuth initialMode="signin" /> : <Outlet />;
}
