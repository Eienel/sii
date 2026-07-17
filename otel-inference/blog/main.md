---
title: "Why is my self-hosted LLM slow? Giving vLLM a causal, OTel-native view in SigNoz"
tags: [observability, opentelemetry, signoz, llm, vllm, sre]
canonical: dev.to
track: "AI & Agent Observability / Signals & Dashboards"
---

> Main submission for the **Agents of SigNoz** hackathon.
> Repo: `otel-inference` — a candidate `gen_ai.server.*` convention + OTTL mapping +
> a causal SigNoz dashboard for self-hosted inference. Proven on a free Kaggle T4,
> across vLLM **and** Ollama.

## The gap

If you run your own inference (vLLM, Ollama, TGI, SGLang) to cut API costs, you
eventually hit the question: **why is p99 latency spiking?** The existing OTel
GenAI conventions cover *client-side* call metrics and request/token timing. They
do **not** standardize the *server-internal* state that actually answers the
question:

- KV / **prefix-cache hit-rate** and evictions,
- scheduler **queue wait** and depth,
- the **prefill vs decode** phase split.

These are proposed in
[semantic-conventions-genai#87](https://github.com/open-telemetry/semantic-conventions-genai#87)
but marked *"not in scope (for now)."* So every engine names them differently, and
the write-ups that exist (great ones from Parseable and Dash0) stop at *"scrape
`/metrics`, draw gauges."* Gauges tell you *that* it's slow. They don't tell you
*why*, and they don't survive switching engines.

## The idea: make the un-standardized signals a portable primitive

`otel-inference` is three small things:

1. **A candidate `gen_ai.server.*` convention** — one name per concept, whatever the
   engine emits.
2. **An OTTL mapping** in the OpenTelemetry Collector that rewrites each engine's
   raw metric names into that convention. Adding an engine = adding `where` clauses.
3. **A causal SigNoz dashboard** that decomposes a latency spike into its cause and
   drills into the individual slow **traces** that confirm it.

```
vLLM (--enable-prefix-caching, --otlp-traces-endpoint)
  ├─ /metrics ─┐
  └─ traces ───┼─► OTel Collector ──[transform/OTTL: raw → gen_ai.server.*]──► SigNoz
GPU (pynvml) ──┘
```

The mapping is the whole trick, and it's tiny:

```yaml
# collector/ottl/vllm.yaml
- set(name, "gen_ai.server.kv_cache.hits")       where name == "vllm:prefix_cache_hits"
- set(name, "gen_ai.server.kv_cache.queries")    where name == "vllm:prefix_cache_queries"
- set(name, "gen_ai.server.queue.wait_duration") where name == "vllm:request_queue_time_seconds"
- set(name, "gen_ai.server.prefill.duration")    where name == "vllm:request_prefill_time_seconds"
- set(name, "gen_ai.server.decode.duration")     where name == "vllm:request_decode_time_seconds"
# ...
```

> **Design note:** hit-rate is *not* precomputed. `hits`/`queries` are
> token-granularity counters, so the only correct rolling ratio is
> `rate(hits)/rate(queries)` — computed as a **formula in the dashboard**, not
> baked into a wrong gauge.

## The causal dashboard

Four rows, top-to-bottom = symptom → cause:

| Row | Panels | Reads as |
|---|---|---|
| **Symptom** | e2e latency p99, TTFT p95 | "something is slow" |
| **Cause A — scheduler** | running vs queued, queue-wait p95 | "requests are piling up" |
| **Cause B — cache** | hit-rate = `rate(hits)/rate(queries)` | "more prefill compute per request" |
| **Cause C — phase** | prefill vs decode p95 | "which phase is the bottleneck" |
| **Hardware** | GPU util, GPU mem | "is it a compute wall" |

Then you click the spike and land on the actual slow **trace**, whose
`gen_ai.latency.time_in_queue` confirms the story. Aggregate metric → individual
trace, one investigation. That's the SigNoz correlation I fell for in the pre-event
post, now pointed at the hardest question in self-hosted inference.

## Reproducing it (free GPU)

The whole thing runs on a **free Kaggle T4** — `notebooks/kaggle_vllm.ipynb` boots
vLLM, the GPU exporter, the collector, and a load generator that stages an incident
on purpose:

- **WARM** — shared-prefix prompts, low concurrency → high hit-rate, healthy.
- **SPIKE** — unique long prompts, high concurrency → hit-rate collapses *and* the
  queue backs up → TTFT and e2e latency spike.
- **RECOVER** — back to shared prefixes → cache warms, queue drains.

Watching the dashboard, the SPIKE isn't just "latency went red" — you *see* the
hit-rate line fall and the queue-wait line rise in lockstep, and the phase panel
tells you it's prefill-bound. Cause, not vibes.

## Layer or primitive? The Ollama test

The cheap way to prove this isn't just a vLLM wrapper: populate the **same**
convention — and therefore the same dashboard and alerts — from **Ollama**, by
editing only `where` clauses (`collector/ottl/ollama.yaml`). Nothing in
`dashboards/` changes.

Some `gen_ai.server.*` cells stay **empty** for Ollama (no prefix-cache counters,
no prefill/decode split) — and that absence is *information*: a shared convention
surfaces engine capability gaps through one lens instead of forcing you to learn
each engine's private vocabulary. That's the difference between a layer that dies
when the engine changes and a primitive other engines plug into.

## What's honestly done vs next

- **Done:** the convention, the OTTL mapping (vLLM + Ollama stub), GPU exporter,
  load generator, causal dashboard, two alerts (queue-wait, hit-rate collapse),
  self-host + Cloud paths, Kaggle notebook.
- **Next:** upstreaming feedback to issue #87, TGI/SGLang `where` blocks, and cache
  **eviction** counters once engines expose them.

## Try it

```bash
git clone https://github.com/Eienel/sii
cd sii/otel-inference && cat README.md
```

Built for Agents of SigNoz. The point was never a prettier gauge — it was making
"why is my LLM slow?" a question one dashboard can actually answer, on any engine.
