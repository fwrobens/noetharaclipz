import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ getSession: vi.fn() }));
vi.mock("@/lib/supabase/client", () => ({ supabase: { auth: mocks } }));
import {
  consentActive,
  parseConsent,
  requestProcessingConsent,
  requireBetaAdmission,
  withdrawProcessingConsent,
} from "@/lib/processing-consent";

const id = "11111111-1111-4111-8111-111111111111";
const consent = {
  owner_id: id,
  consent_id: id,
  approved_at: "2026-01-01T00:00:00Z",
  expires_at: "2099-01-01T00:00:00Z",
  revoked_at: null,
};
const fetchMock = vi.fn();
beforeEach(() => {
  mocks.getSession.mockResolvedValue({
    data: { session: { access_token: "test-owner-session" } },
    error: null,
  });
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
});
afterEach(() => vi.unstubAllGlobals());
describe("owner processing consent", () => {
  it("fails closed on expired, revoked, future, missing or malformed approval", () => {
    const now = Date.parse("2026-11-11T00:00:00Z");
    expect(consentActive(parseConsent(consent), now)).toBe(true);
    for (const c of [
      null,
      { ...consent, approved_at: null },
      { ...consent, expires_at: "2026-01-01T00:00:00Z" },
      { ...consent, revoked_at: consent.approved_at },
      { ...consent, approved_at: "2098-01-01T00:00:00Z" },
    ])
      expect(consentActive(c, now)).toBe(false);
    expect(() => parseConsent({ ...consent, expires_at: "bad" })).toThrow();
    expect(() => parseConsent([])).toThrow();
  });
  it("records nothing without explicit consent or authentication", async () => {
    await expect(requestProcessingConsent(id, false)).rejects.toThrow("Confirm");
    mocks.getSession.mockResolvedValue({ data: { session: null }, error: null });
    await expect(requestProcessingConsent(id, true)).rejects.toThrow("Sign in");
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it("requests consent with the owner's JWT and no operator or owner override", async () => {
    fetchMock.mockResolvedValue(Response.json({ ...consent, approved_at: null, expires_at: null }));
    await requestProcessingConsent(id, true);
    const [url, opts] = fetchMock.mock.calls[0]!;
    expect(url).toMatch(/\/rpc\/request_processing_consent$/);
    expect(JSON.parse(opts.body)).toEqual({ request_id: id, terms_version: "local-video-v1" });
    expect(opts.headers.Authorization).toBe("Bearer test-owner-session");
  });
  it("withdraws only the current consent generation", async () => {
    fetchMock.mockResolvedValue(Response.json(true));
    await withdrawProcessingConsent(id);
    expect(fetchMock.mock.calls[0]![0]).toMatch(/\/rpc\/revoke_processing_consent$/);
    expect(JSON.parse(fetchMock.mock.calls[0]![1].body)).toEqual({ consent: id });
  });
  it("refuses beta upload admission without approval or a ready scoped worker", async () => {
    fetchMock.mockResolvedValueOnce(Response.json(null));
    await expect(requireBetaAdmission()).rejects.toThrow("active beta approval");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    fetchMock
      .mockResolvedValueOnce(Response.json(consent))
      .mockResolvedValueOnce(Response.json({ online: true, ai_ready: false }));
    await expect(requireBetaAdmission()).rejects.toThrow("temporarily unavailable");
    fetchMock
      .mockResolvedValueOnce(Response.json(consent))
      .mockResolvedValueOnce(Response.json({ online: true, ai_ready: true }));
    await expect(requireBetaAdmission()).resolves.toBeUndefined();
  });
});
