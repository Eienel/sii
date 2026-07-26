# otel-inference

**OpenTelemetry-native observability for self-hosted LLM inference — the causal layer.**

Built for the [Agents of SigNoz](https://www.wemakedevs.org/hackathons/signoz)
hackathon — tracks **AI & Agent Observability** and **Signals & Dashboards**.

> **Install SigNoz via [Foundry](https://github.com/SigNoz/foundry)** (the
> hackathon-required, reproducible install path). See [`casting.yaml`](../casting.yaml)
> and [AI use disclosure](../AI_DISCLOSURE.md).

---

## The problem (the seam nobody owns yet)

vLLM already ships native OpenTelemetry **tracing** (`--otlp-traces-endpoint`) and a
Prometheus `/metrics` endpoint. Existing write-ups (Parseable, Dash0) stop at
"scrape `/metrics` → draw some gauges." That tells you *that* latency went up. It
does not tell you **why**.

The high-leverage server-internal signals — **KV-cache hit-rate & evictions**,
**queue wait time**, **prefill vs decode** breakdown — are proposed for the
OpenTelemetry GenAI semantic conventions in
[`semantic-conventions-genai#87`](https://github.com/open-telemetry/semantic-conventions-genai/issues/87)
but are still marked *"not in scope / unstandardized."* So today:

- every engine names these metrics differently (`vllm:prefix_cache_hits`,
  Ollama's own names, TGI's own names),
- you can't build one cross-engine dashboard or alert,
- and the per-request **traces** are never correlated with the server-internal
  **metric state** that actually explains a slow request.

## What this repo is

A small, reusable **primitive**:

1. **A candidate `gen_ai.server.*` convention** ([`convention/`](convention/)) that
   mirrors issue #87, so KV-cache / queue / prefill-decode signals have *one* name
   regardless of engine.
2. **An OTTL mapping ruleset** ([`collector/ottl/`](collector/ottl/)) that rewrites
   each engine's raw metrics into that convention inside the OpenTelemetry
   Collector — declarative, versioned, engine-pluggable.
3. **A causal SigNoz dashboard** ([`dashboards/`](dashboards/)) that decomposes a
   latency spike into its cause (queue wait ↑ / cache hit-rate ↓ / decode stall)
   and drills into the individual slow **traces** that confirm it.
4. **A GPU exporter** ([`gpu_exporter/`](gpu_exporter/)) and **load generator**
   ([`loadgen/`](loadgen/)) so you can reproduce the whole causal story on a free
   Kaggle T4.
5. **Cross-engine proof**: the same convention + dashboard populated from **Ollama**
   ([`adapters/`](adapters/)) — layer vs primitive, settled.

## Architecture

```
vLLM (--enable-prefix-caching, --otlp-traces-endpoint)
  ├─ /metrics (Prometheus) ─┐
  └─ native OTel traces ────┼─► OpenTelemetry Collector (contrib)
Ollama /metrics ────────────┤     receivers:  prometheus, otlp
GPU exporter (pynvml) OTLP ─┘     processors: transform (OTTL) ← the convention
                                  exporters:  otlp → SigNoz Cloud   (primary)
                                              otlp → local SigNoz   (self-host/blog)
load generator (asyncio+httpx): shared-prefix vs unique prompts + concurrency ramp
```

Aggregate server state comes from **metrics**; per-request causality comes from
vLLM's existing **trace span attributes** (`gen_ai.latency.time_in_queue`, TTFT).
The dashboard aligns the two. No custom span plumbing — we stand on what vLLM
already emits.

## Quickstart

**Free-GPU path:** follow [`docs/RUNNING_ON_KAGGLE.md`](docs/RUNNING_ON_KAGGLE.md)
(step-by-step, ~15 min) with [`notebooks/kaggle_vllm.ipynb`](notebooks/kaggle_vllm.ipynb).

Or run locally:

```bash
# 1. self-hosted SigNoz (for the pre-event blog / data ownership)
docker compose -f deploy/docker-compose.signoz.yaml up -d

# 2. serve a small model with prefix caching + native traces
vllm serve Qwen/Qwen2.5-0.5B-Instruct \
  --enable-prefix-caching \
  --otlp-traces-endpoint http://localhost:4317

# 3. GPU metrics sidecar
python gpu_exporter/gpu_otel.py --endpoint http://localhost:4317

# 4. collector applying the convention
otelcol-contrib --config collector/otelcol-config.yaml

# 5. drive load that forces cache hits + queue pressure
python loadgen/generate.py --base-url http://localhost:8000 --ramp

# 6. import the dashboard
#    SigNoz → Dashboards → Import → dashboards/inference_causal.json
```

Configure the SigNoz Cloud sink via env (`SIGNOZ_CLOUD_ENDPOINT`,
`SIGNOZ_INGESTION_KEY`) — see [`collector/otelcol-config.yaml`](collector/otelcol-config.yaml).

## Repo layout

| Path | What |
|---|---|
| `convention/` | The candidate `gen_ai.server.*` semantic convention (mirrors #87) |
| `collector/otelcol-config.yaml` | Collector pipeline: receivers → OTTL transform → exporters |
| `collector/ottl/` | Per-engine mapping rules (`vllm.yaml`, `ollama.yaml`) |
| `gpu_exporter/gpu_otel.py` | pynvml → OTLP GPU metrics |
| `loadgen/generate.py` | asyncio load: prefix-cache hits + queue backpressure |
| `adapters/` | Ollama one-engine stub (primitive proof) |
| `dashboards/inference_causal.json` | Importable SigNoz causal dashboard |
| `alerts/` | Queue-wait p95 + cache-hit-rate-drop alert definitions |
| `deploy/docker-compose.signoz.yaml` | Self-hosted SigNoz |
| `notebooks/kaggle_vllm.ipynb` | Free-GPU runnable setup |
| `blog/` | Pre-event (self-host) + main (convention) blog drafts |

## Status (read this before judging the dashboard)

- **Authored + committed:** convention spec, OTTL mapping (vLLM + Ollama stub), GPU
  exporter, load generator, causal dashboard JSON, alerts, Foundry/Cloud paths,
  Kaggle notebook.
- **Validated without a GPU:** collector config + OTTL rules pass `otelcol validate`;
  load generator smoke-tested against a mock OpenAI-compatible server; GPU exporter
  exits cleanly where no NVML exists.
- **Pending real hardware:** vLLM metric names are pinned from the v1 engine and
  re-checked at runtime by the notebook's `FOUND`/`MISSING` kill-probe (names drift
  between versions — that probe is why a drift is a one-line OTTL fix). Dashboard
  thresholds are stated hypotheses, not values observed on a live run.
