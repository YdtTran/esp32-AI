# 0005: Speaches GPU development deployment

- Date: 2026-10-14
- Status: Accepted
- Owners: infrastructure maintainer and AI module responsibility

## Context

The user requested a standalone Speaches Docker deployment on Windows with
Docker Desktop/WSL2 and an NVIDIA RTX 2050 (4 GB VRAM), without model downloads
or inference pipelines. Existing infrastructure provides isolated host checks.
This request authorizes the development runtime and service organization only.

## Decision

Use the official `ghcr.io/speaches-ai/speaches:latest-cuda` image, pinned to the
pulled digest `sha256:6ec12ebf890a17e0d4b242a8ba9e0eb1fb836e60e8a3c857aea9838d541579ac`, with an NVIDIA
GPU reservation and a service-specific persistent Hugging Face hub cache volume.
The root Compose entry point includes service-owned Compose files. Preserve the
foundation validation service under an on-demand `checks` profile and retain its
Dockerfile at the path required by the existing repository validator.

Expose port 8000 on localhost only. Explicitly disable model preloading and the
Gradio UI. Set documented Whisper CUDA/int8 options and 60-second STT/TTS idle
unloading for later use; no model is selected. No shared interface, device
transport, inference adapter, remote access or production authentication is
defined. Other Docker projects are outside this deployment.

## Alternatives

A CPU image does not meet the requested GPU deployment. Building Speaches from
source is unnecessary when an official image exists. A single growing Compose
file obscures service ownership. Moving the foundation Dockerfile would require
an unrelated validator change.

## Consequences

The CUDA image consumes disk space even with no models. The cache survives
container recreation; `down --volumes` deletes it. Roll back by stopping/removing
only Speaches and reverting its include; the foundation configuration remains.
Compose include requires version 2.20.3+. Local unauthenticated access is for
development. Four GB VRAM does not guarantee future model/concurrency capacity.
Production deployment, model selection and other service decisions remain open.

## Validation

Verified on 2026-10-14 with Docker Desktop 4.95.0, Engine 29.8.2 and Compose
5.6.0:

- `docker pull ghcr.io/speaches-ai/speaches:latest-cuda` succeeded; the pinned
  digest above is the pulled image (CUDA 12.6.3).
- `docker compose -f infrastructure/compose.yaml config --quiet` passed.
  Configuration also passed with `--env-file infrastructure/.env.example` and
  using `-f infrastructure/services/speaches/compose.yaml` independently.
- `docker compose -f infrastructure/compose.yaml --profile checks config`
  confirmed the preserved foundation build context and Dockerfile path.
- `docker compose -f infrastructure/compose.yaml up -d --wait --wait-timeout 120 speaches`
  succeeded; `docker compose -f infrastructure/compose.yaml ps speaches` showed
  `infrastructure-speaches-1` healthy, published on `127.0.0.1:8000`.
- `docker compose -f infrastructure/compose.yaml exec -T speaches nvidia-smi`
  detected NVIDIA GeForce RTX 2050 with 4096 MiB memory. Container inspection
  confirmed an NVIDIA device request with one GPU.
- `Invoke-WebRequest -Uri http://localhost:8000/health` and the same command for
  `/openapi.json` returned HTTP 200. Container logs showed successful startup.
- `docker compose -f infrastructure/compose.yaml exec -T speaches sh -c 'find /home/ubuntu/.cache/huggingface/hub -type f'`
  returned no files. No model installation or inference request was made.
- Existing containers retained their IDs; ThingsBoard, PostgreSQL and the
  ThingsBoard MCP container retained their start times. n8n remained stopped.
  The unrelated Maix camera container was already restarting before setup and
  continued restarting; it was not changed by this deployment.
- `python scripts/validate.py` passed foundation checks and all seven existing
  tests. Firmware builds, hardware audio checks and model inference were skipped
  because they are outside this infrastructure-only request. The optional
  foundation Docker image was not rebuilt; its Compose paths were checked.

GPU visibility and API health do not establish model inference or capacity.

Sources: [official Docker installation](https://speaches.ai/installation/),
[official CUDA Compose](https://github.com/speaches-ai/speaches/blob/master/compose.cuda.yaml),
[configuration](https://speaches.ai/configuration/).
