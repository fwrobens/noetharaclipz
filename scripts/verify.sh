#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
npm ci
npx tsc --noEmit
npm test
npm run lint
npm run build
uv sync --project worker --frozen
uv run --project worker ruff check worker
uv run --project worker pytest worker/tests -q
# Set NC_SAMPLE_VIDEO to an authorized file to include the actual transcription integration test.
# AI acceptance requires a configured free Gemini project and a real worker; no stubs substitute.
