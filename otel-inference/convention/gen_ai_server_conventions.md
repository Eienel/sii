# `gen_ai.server.*` — candidate semantic convention for self-hosted inference

**Version:** 0.1.0
**Status:** candidate / experimental — a concrete implementation of the metrics
proposed (but not yet standardized) in
[open-telemetry/semantic-conventions-genai#87](https://github.com/open-telemetry/semantic-conventions-genai#87).

## Why this exists

The OpenTelemetry GenAI conventions today standardize *client-side* call metrics
(`gen_ai.client.*`) and request duration / token timing. They do **not** cover the
**server-internal** state of a self-hosted inference engine — KV-cache behavior,
scheduler queue state, and the prefill-vs-decode phase split — which is exactly
what explains *why* a self-hosted deployment is slow.

Because there's no shared convention, every engine names these differently and you
cannot build one dashboard or alert that works across vLLM, Ollama, TGI, SGLang.
This document defines a minimal, engine-agnostic set so you can.

## Resource / datapoint attributes

| Attribute | Type | Notes |
|---|---|---|
| `gen_ai.system` | string | `vllm`, `ollama`, `tgi`, `sglang`, … (reuses the existing GenAI attribute) |
| `gen_ai.request.model` | string | served model id |
| `gen_ai.convention.version` | string | set by the collector (`0.1.0`) so consumers can pin a schema |

## Metrics

### KV / prefix cache
| Metric | Instrument | Unit | Meaning |
|---|---|---|---|
| `gen_ai.server.kv_cache.usage_ratio` | Gauge | 1 | fraction of KV cache blocks in use (0–1) |
| `gen_ai.server.kv_cache.hits` | Counter | tokens | prompt tokens served from prefix cache |
| `gen_ai.server.kv_cache.queries` | Counter | tokens | prompt tokens looked up in prefix cache |
| `gen_ai.server.kv_cache.hit_rate` | Gauge | 1 | optional; if the engine exposes a ready ratio |
| `gen_ai.server.kv_cache.evictions` | Counter | blocks | optional; cache blocks evicted |

> **Hit-rate is derived, not stored.** With token-granularity counters the correct
> rolling ratio is `rate(hits) / rate(queries)`. Precomputing a gauge in the
> collector would be wrong across scrape intervals. Compute it in the dashboard.

### Queue / scheduling
| Metric | Instrument | Unit | Meaning |
|---|---|---|---|
| `gen_ai.server.requests.running` | UpDownCounter | requests | in-batch requests |
| `gen_ai.server.requests.queued` | UpDownCounter | requests | waiting requests (leading overload indicator) |
| `gen_ai.server.queue.wait_duration` | Histogram | s | time a request spent waiting before prefill |
| `gen_ai.server.preemptions` | Counter | requests | scheduler preemptions (memory pressure) |

### Prefill vs decode
| Metric | Instrument | Unit | Meaning |
|---|---|---|---|
| `gen_ai.server.prefill.duration` | Histogram | s | time in prefill phase |
| `gen_ai.server.decode.duration` | Histogram | s | time in decode phase |

### Request-level latency (symptom row)
| Metric | Instrument | Unit | Meaning |
|---|---|---|---|
| `gen_ai.server.request.duration` | Histogram | s | end-to-end request latency |
| `gen_ai.server.time_to_first_token` | Histogram | s | TTFT |
| `gen_ai.server.time_per_output_token` | Histogram | s | inter-token latency |

### GPU (host of the engine)
| Metric | Instrument | Unit | Meaning |
|---|---|---|---|
| `gen_ai.server.gpu.utilization` | Gauge | 1 | SM utilization (0–1) |
| `gen_ai.server.gpu.memory.used` | Gauge | By | device memory used |
| `gen_ai.server.gpu.power.usage` | Gauge | W | board power draw |

## The causal chain (why these metrics, together)

```
symptom:  gen_ai.server.request.duration ↑ / time_to_first_token ↑
   │
   ├─ cause A (scheduler):  requests.queued ↑  →  queue.wait_duration ↑
   ├─ cause B (cache):      hit_rate ↓  →  more prefill compute
   ├─ cause C (phase):      prefill.duration ↑  vs  decode.duration ↑
   └─ cause D (hardware):   gpu.utilization saturated / memory.used near limit
```

Per-request confirmation comes from vLLM's native **trace spans**
(`gen_ai.latency.time_in_queue`, TTFT attributes) — the dashboard links a spike in
the aggregate metric to the individual slow traces that caused it.

## Engine coverage

| Metric group | vLLM | Ollama (stub) |
|---|---|---|
| KV/prefix cache | ✅ | ⬜ (not exposed) |
| queue/scheduling | ✅ | partial |
| prefill/decode split | ✅ | ⬜ |
| request latency | ✅ | ✅ |
| GPU | ✅ (sidecar) | ✅ (sidecar) |

Empty cells are meaningful: they show engine capability gaps through one lens
instead of forcing you to learn each engine's private metric vocabulary.
