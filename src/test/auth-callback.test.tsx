import { StrictMode, type ComponentType } from "react";
import { render, screen, cleanup } from "@testing-library/react";
import { beforeEach, afterEach, describe, it, expect, vi } from "vitest";
const { exchange, signOut, identity, finish } = vi.hoisted(() => ({
  exchange: vi.fn(),
  signOut: vi.fn(),
  identity: vi.fn(),
  finish: vi.fn(),
}));
vi.mock("@/lib/supabase/client", () => ({
  supabase: { auth: { exchangeCodeForSession: exchange, signOut } },
}));
vi.mock("@/lib/auth.functions", () => ({ fetchIdentity: identity }));
vi.mock("@/lib/auth-callback", async (original) => ({
  ...(await original<typeof import("@/lib/auth-callback")>()),
  finishAuthCallback: finish,
}));
vi.mock("@tanstack/react-router", async (original) => ({
  ...(await original<typeof import("@tanstack/react-router")>()),
  Link: ({ children }: { children: React.ReactNode }) => <a>{children}</a>,
}));
import { PRODUCTION_AUTH_CALLBACK, authCallbackUrl } from "@/lib/auth-callback";
import { Route } from "@/routes/auth.callback";
const Callback = Route.options.component as ComponentType;
beforeEach(() => {
  exchange.mockReset();
  signOut.mockReset();
  identity.mockReset();
  finish.mockReset();
  window.history.replaceState({}, "", "/auth/callback");
});
afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});
describe("PKCE callback ownership", () => {
  it("consumes the single-use code once in StrictMode and forwards its flow id", async () => {
    window.history.replaceState({}, "", "/auth/callback?code=unit-code&sb_flow_id=flow-id");
    exchange.mockResolvedValue({ error: { message: "Expired QA link" } });
    render(
      <StrictMode>
        <Callback />
      </StrictMode>,
    );
    await screen.findByText("Expired QA link");
    expect(exchange).toHaveBeenCalledTimes(1);
    expect(exchange).toHaveBeenCalledWith("unit-code", { flowId: "flow-id" });
  });
  it("does not exchange a missing code", () => {
    render(<Callback />);
    expect(exchange).not.toHaveBeenCalled();
    expect(screen.getByRole("status")).toHaveTextContent("missing its code");
  });
  it("handles transport rejection without an unhandled promise", async () => {
    window.history.replaceState({}, "", "/auth/callback?code=unit-code");
    exchange.mockRejectedValue(new Error("offline"));
    render(<Callback />);
    await screen.findByText("Sign in could not be completed. Return to sign in and try again.");
  });
  it("shows a provider error without exchanging the code", () => {
    window.history.replaceState(
      {},
      "",
      "/auth/callback?error=access_denied&error_description=Email%20link%20is%20invalid%20or%20has%20expired",
    );
    render(<Callback />);
    expect(exchange).not.toHaveBeenCalled();
    expect(screen.getByRole("status")).toHaveTextContent("Email link is invalid or has expired");
  });
  it("opens the dashboard after a successful production PKCE exchange", async () => {
    window.history.replaceState({}, "", "/auth/callback?code=unit-code");
    exchange.mockResolvedValue({ error: null });
    render(<Callback />);
    await vi.waitFor(() => expect(finish).toHaveBeenCalledOnce());
    expect(identity).not.toHaveBeenCalled();
    expect(signOut).not.toHaveBeenCalled();
  });
  it("signs an uninvited beta callback out instead of opening the dashboard", async () => {
    vi.stubEnv("VITE_NC_BETA_MODE", "true");
    window.history.replaceState({}, "", "/auth/callback?code=unit-code");
    exchange.mockResolvedValue({ error: null });
    identity.mockResolvedValue(null);
    signOut.mockResolvedValue({ error: null });
    render(<Callback />);
    await screen.findByText("Beta access could not be verified. Use your invited account or retry later.");
    expect(signOut).toHaveBeenCalledWith({ scope: "local" });
    expect(finish).not.toHaveBeenCalled();
  });
});
describe("production auth callback URL", () => {
  it("is the exact allow-listed production callback and adds no query", () => {
    expect(authCallbackUrl("https://noetharaclipz.lovable.app")).toBe(PRODUCTION_AUTH_CALLBACK);
    expect(new URL(PRODUCTION_AUTH_CALLBACK).search).toBe("");
    expect(authCallbackUrl("http://localhost:3000")).toBe("http://localhost:3000/auth/callback");
    expect(() => authCallbackUrl("https://noetharaclipz.lovable.app/extra")).toThrow();
  });
});
