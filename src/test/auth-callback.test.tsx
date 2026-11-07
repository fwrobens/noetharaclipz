import { StrictMode, type ComponentType } from "react";
import { render, screen, cleanup } from "@testing-library/react";
import { beforeEach, afterEach, describe, it, expect, vi } from "vitest";
const { exchange } = vi.hoisted(() => ({ exchange: vi.fn() }));
vi.mock("@/lib/supabase/client", () => ({
  supabase: { auth: { exchangeCodeForSession: exchange } },
}));
vi.mock("@tanstack/react-router", async (original) => ({
  ...(await original<typeof import("@tanstack/react-router")>()),
  Link: ({ children }: { children: React.ReactNode }) => <a>{children}</a>,
}));
import { Route } from "@/routes/auth.callback";
const Callback = Route.options.component as ComponentType;
beforeEach(() => {
  exchange.mockReset();
  window.history.replaceState({}, "", "/auth/callback");
});
afterEach(() => cleanup());
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
});
