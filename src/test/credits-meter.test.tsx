import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, ...props }: { children?: React.ReactNode }) => <a {...props}>{children}</a>,
  useNavigate: () => vi.fn(),
  useRouterState: () => "/dashboard",
  useRouteContext: () => ({ queryClient: { cancelQueries: vi.fn(), clear: vi.fn() } }),
}));
vi.mock("@/lib/supabase/client", () => ({
  supabase: { auth: { signOut: vi.fn() } },
}));

import { CREDITS, CREDITS_METER_LABEL, DashboardShell } from "@/components/dashboard/DashboardShell";

describe("credits meter", () => {
  it("keeps the published sample numbers and labels them as a demonstration", () => {
    render(
      <DashboardShell displayName="Avery" projectCount={2}>
        <p>Workspace</p>
      </DashboardShell>,
    );
    expect(CREDITS).toEqual({ remaining: 120, total: 150 });
    expect(screen.getAllByText("120").length).toBeGreaterThan(0);
    expect(screen.getByText("/ 150")).toBeInTheDocument();
    expect(screen.getAllByText("Demo").length).toBeGreaterThan(0);
    expect(screen.getByText(CREDITS_METER_LABEL)).toBeInTheDocument();
    expect(screen.getByText("Top up credits")).toBeInTheDocument();
  });
});
