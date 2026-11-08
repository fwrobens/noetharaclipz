# Follow-up: credentials, provider eligibility, and real video verification

## Credential-equipped follow-up

The [new credential-backed verification](credential-backed-verification.md)
supersedes the runtime-binding, model-access and private-download blockers below.
The configured environment now validates the real Supabase worker credential,
Gemini model metadata and NVIDIA NVCF authentication. Independent live media
processing and a browser private-MP4 download succeeded using a manual QA
interval. The false Gemini flag remains unchanged; free account eligibility and
automatic AI selection are still unverified. The live database heartbeat RPC
also requires the [authorized scoped function correction](heartbeat-repair.md),
which now passes real credential-backed checks; its filename matches the operator-reported deployed version.

The remaining sections preserve the earlier task's observations and must not be
read as a current absence of credentials in the configured environment.

## Earlier implementation task environment

The user reports that all nine requested variables are saved in Codex Cloud Personal Vault. Fresh shell commands and the managed runtime status still show **no bindings in this running instance**:

- Environment ID: `ccarenv_b64_Y2NhcmVudl9kZTI3Njk0Mjg1ZGM4MTkxYjE5ZTE3MjAyZWZjYWZmMg`.
- `source_config_id: null`, `source_config_version_id: null`, spec/applied revision `1`.
- `observations_current: true`, running, unrestricted network policy enforced.
- Empty `secrets` and `runtime_variables` collections.
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`, `GEMINI_FREE_TIER_VERIFIED`, all three Gemini quota variables, `ANYMODEL_API_KEY`, and `NVIDIA_API_KEY` are absent from fresh child processes. The new optional alias `SUPABASE_SECRET_KEY` is absent too.

This is a **vault-to-task configuration binding issue**, not a conclusion that the saved keys are missing or invalid. The user should select/apply the configured environment to this task; the vault values need not be recreated or pasted. The current toolset has runtime inspection but no configuration-write/binding operation. A referenced setup-thread link could not be inspected because `read_thread` is not exposed in this session; no conclusions rely on unread task contents.

`GEMINI_FREE_TIER_VERIFIED=false` is intentional. It remains false by default and is never changed by the worker. Even a true flag and positive environment numbers would only be operator assertions; API model metadata cannot establish account billing status, eligibility, or actual remaining quota.

## Supabase

The connected Supabase integration independently confirms the existing NoetharaClipZ project is `ACTIVE_HEALTHY`, with six migrations, ten RLS-protected application tables, five private buckets, and no pending jobs or recorded hosted inference.

The worker now uses modern opaque server keys correctly on `apikey` without treating them as bearer JWTs. Legacy service-role JWTs retain the legacy header pair. Public/user keys and malformed credentials are rejected before use; actual authentication must still be validated remotely. HTTP contract tests cover both formats for RPC, uploads, and downloads, without claiming real credential validation.

Hosted transactional tests pass, now including expired-job reclaim with a new lease and rejection of the old token. They use the connected administrative integration, not a runtime worker credential. **They do not establish that this Python worker can authenticate or upload/download private media.** That live test remains blocked until the binding issue is resolved.

## Google Gemini

Official references reviewed:

- https://ai.google.dev/gemini-api/terms
- https://ai.google.dev/gemini-api/docs/rate-limits
- https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash

The configured adapter targets documented video-capable Gemini 3.8 Flash. Model access for this account has not been validated, because the key is not bound here. Model metadata inspection is now separate from inference authorization, allowing a safe metadata-only check once the key is injected while retaining the false generation gate.

Material terms include age 18+, eligible regions, and API Clients not directed toward or likely to be accessed by under-18 users. API Clients made available to users in the EEA, Switzerland, or UK require Paid Services under the current terms. Unpaid content may be used for product improvement/human review; sensitive/confidential/personal content is excluded. Account/project limits must be confirmed in AI Studio; they are not inferred from model catalogs or published examples. No billing or inference was activated.

## NVIDIA

The public catalog at https://integrate.api.nvidia.com/v1/models is reachable without a key. It lists `nvidia/cosmos-reason2-8b` and `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`, among others. The Cosmos Reason2 model page exposes a `video_url` content schema, establishing an actual video interface rather than assuming image support implies video support.

This is **public catalog availability**, not authentication, a credit balance, remaining quota, or permission for production use. The configured NVIDIA key is not bound to this runtime, so those account checks could not be performed.

The model page links the NVIDIA API Trial Terms of Service:
https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf

Sections 1.2–1.4 restrict trial services and their outputs to internal testing/evaluation, prohibit production use, and describe finite trial credits. A separate subscription is required after trial credits or for production. No credit purchase, subscription, endpoint switch, or inference call was attempted.

## AnyModel

No connected AnyModel tool was found, and plugin discovery returned no matching integration. No verified base URL/account metadata is available in this task; candidate public documentation endpoints could not establish an official free video-capable API. The vault key is not injected here. Authentication, modalities, pricing and quotas are therefore **unverified**. No key was sent to an unverified endpoint and no model was selected based on a guessed free tier.

## Local open-source multimodal proof

A genuine CPU video inference ran using Apache-2.0, ungated `HuggingFaceTB/SmolVLM2-500M-Video-Instruct`, pinned to revision `7b375e1b73b11138ff12fe22c8f2822d8fe03467`. Model card: https://huggingface.co/HuggingFaceTB/SmolVLM2-500M-Video-Instruct

The probe used the authorized Sintel trailer's 11–21 second interval, actual decoded video tensors `[1, 4, 3, 512, 512]`, and local CPU PyTorch. The recorded run used 372 input tokens, generated 25 tokens in 11.41 seconds, and described visible characters/actions. Raw output and provenance are in [local evidence](evidence/local-smolvlm2-sintel.json).

**This proves real local visual/video inference, not reliable AI highlight selection.** The description has coarse scene-level interpretations and has not passed timestamp/quality evaluation. It is not integrated as an automatic fallback and is not saved as an AI-selected highlight. Scene/audio detection remains heuristic evidence; Whisper is genuine speech inference; these stages are clearly distinguished.

Reproduce in an isolated optional research environment (does not alter the worker's pinned dependencies):

```sh
uv venv /tmp/nc-vlm-env
uv pip install --python /tmp/nc-vlm-env/bin/python torch==2.9.0 torchvision==0.24.0 --index-url https://download.pytorch.org/whl/cpu
uv pip install --python /tmp/nc-vlm-env/bin/python -r scripts/requirements-local-video.txt --index-url https://pypi.org/simple
HF_HUB_DISABLE_XET=1 /tmp/nc-vlm-env/bin/python scripts/local_video_probe.py /path/to/authorized/sintel.mp4
```

It uses no hosted inference, no API key, no remote Python model code, no GPU provisioning, and no paid service. The model weights occupy about 1.9 GB of cache plus the CPU research environment; this workspace had sufficient RAM/disk for the tested short interval. An always-on production worker has not been provisioned.

## Fixes and release gate

- Modern Supabase key transport; environment values are read and validated when worker settings are created.
- Independent Gemini metadata inspection, keeping unverified inference blocked.
- Storage cleanup snapshots all pages before removing subfolders, avoiding skipped objects when pagination shifts.
- Worker health heartbeat runs independently of long jobs. Graceful shutdown stops work and leaves the lease recoverable, instead of falsely marking the job failed/cancelled.
- PKCE callback owns the single-use code exchange; SDK URL auto-detection is disabled to prevent double exchange, StrictMode is guarded, flow IDs are forwarded, and transport failures are handled.
- Transient Auth transport failures produce a retryable error instead of incorrectly treating the user as signed out.

Follow-up verification: 37 worker tests with the authorized sample, 15 frontend tests, TypeScript, production build, Python lint, and web lint pass (web lint retains 11 Fast Refresh warnings). A fresh Chromium run verifies protected-route redirects, missing/invalid callback errors, no unhandled browser exceptions, and no horizontal overflow at 390 pixels. The hosted SQL suite additionally verifies expired-lease reclamation and stale-token rejection. These checks do not substitute for the blocked live worker/private-download test.

The worker/private-download acceptance test and full browser AI acceptance remain **not passed**. Binding a valid project server credential is required for the independent real queue → media → private render/download test. Hosted AI additionally requires independently confirmed permitted free usage; the local model additionally requires a validated highlight-selection adapter. Draft PR #1 must remain draft, unmerged, and unpublished.
