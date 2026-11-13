import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
const calls = vi.hoisted(() => ({ read: vi.fn(), request: vi.fn(), withdraw: vi.fn() }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: { id: "owner" } }) }));
vi.mock("@/lib/processing-consent", async (original) => ({
  ...(await original<typeof import("@/lib/processing-consent")>()),
  readProcessingConsent: calls.read,
  requestProcessingConsent: calls.request,
  withdrawProcessingConsent: calls.withdraw,
}));
import { ProcessingConsentCard } from "@/components/ProcessingConsent";
let client: QueryClient;
beforeEach(() => {
  vi.clearAllMocks();
  calls.read.mockResolvedValue(null);
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
});
afterEach(() => {
  cleanup();
  client.clear();
});
function show() {
  return render(
    <QueryClientProvider client={client}>
      <ProcessingConsentCard />
    </QueryClientProvider>,
  );
}
it("records no consent on page load and requires the explicit checkbox", async () => {
  show();
  const button = await screen.findByRole("button", { name: "Request processing approval" });
  expect(button).toBeDisabled();
  expect(calls.request).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("checkbox"));
  await waitFor(() => expect(button).toBeEnabled());
  calls.request.mockResolvedValue({});
  fireEvent.click(button);
  await waitFor(() => expect(calls.request).toHaveBeenCalledOnce());
  expect(calls.request.mock.calls[0]![1]).toBe(true);
});
it("shows pending consent without offering an operator approval or another request", async () => {
  calls.read.mockResolvedValue({
    owner_id: "owner",
    consent_id: "pending",
    approved_at: null,
    expires_at: null,
    revoked_at: null,
  });
  show();
  await screen.findByText("Your request is awaiting operator approval.");
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Request processing approval" }),
  ).not.toBeInTheDocument();
  expect(calls.request).not.toHaveBeenCalled();
});
it("withdraws the displayed generation only after a user click", async () => {
  calls.read.mockResolvedValue({
    owner_id: "owner",
    consent_id: "current-generation",
    approved_at: "2026-01-01T00:00:00Z",
    expires_at: "2099-01-01T00:00:00Z",
    revoked_at: null,
  });
  calls.withdraw.mockResolvedValue(undefined);
  show();
  const button = await screen.findByRole("button", { name: "Withdraw processing permission" });
  expect(calls.withdraw).not.toHaveBeenCalled();
  fireEvent.click(button);
  await waitFor(() => expect(calls.withdraw).toHaveBeenCalledExactlyOnceWith("current-generation"));
});
