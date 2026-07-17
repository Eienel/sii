---
title: "I self-hosted SigNoz to watch my own LLM server — here's the one feature that sold me"
tags: [observability, opentelemetry, signoz, llm, vllm]
canonical: dev.to  # publish on Dev.to / Medium / Substack (NOT LinkedIn per rules)
target_date: before 2026-07-19
---

> Pre-event blog for the **Agents of SigNoz** hackathon. Self-host SigNoz, send it
> real data, and write about the feature you liked most. Mine was **trace ⇄ metric
> correlation** — and it's the whole reason the main project exists.

## The 15-minute self-host

SigNoz self-hosts from a single compose bundle:

```bash
git clone -b main https://github.com/SigNoz/signoz.git
cd signoz/deploy/docker
docker compose up -d
# UI at http://localhost:8080, OTLP ingest on 4317/4318
```

That's it — ClickHouse, the query service, the OTel collector, and the frontend
come up together. No per-host agent fees, no seat math, and the telemetry lives in
*my* ClickHouse. For an experiment where I'm about to fire thousands of requests at
a GPU, "I own the data" matters.

## Sending it something real

I didn't want a toy `hello-metric`. I pointed a **self-hosted vLLM** server at it —
vLLM speaks OpenTelemetry natively:

```bash
vllm serve Qwen/Qwen2.5-0.5B-Instruct \
  --enable-prefix-caching \
  --otlp-traces-endpoint http://localhost:4317
```

Within seconds I had per-request **traces** flowing in, and vLLM's Prometheus
`/metrics` (TTFT, KV-cache usage, queue depth) scraping into the same SigNoz.

## The feature that sold me: one place, correlated

I've used stacks where traces live in one tool, metrics in another, and you
eyeball two clocks and pray. In SigNoz, a latency spike on the **metrics** dashboard
and the individual **slow trace** that caused it are the same investigation. I could
see e2e latency climb, click into the exact request, and read its
`gen_ai.latency.time_in_queue` attribute — the *cause*, not just the *symptom*.

That's the thing OpenTelemetry-native design buys you: because everything is OTel,
metrics/traces/logs share attributes and SigNoz can correlate them out of the box.
No glue code, no ID-stitching.

## Why this matters for what's next

Watching that correlation work, the gap jumped out at me: vLLM exposes rich
*server-internal* signals — prefix-cache hit-rate, prefill-vs-decode split, queue
wait — but there's **no shared OpenTelemetry convention** for them yet
([semantic-conventions-genai#87](https://github.com/open-telemetry/semantic-conventions-genai#87)
proposes it, still unstandardized). So you can't build one cross-engine dashboard
that says *why* an inference server is slow.

That's exactly what I'm building for the hackathon: a small convention +
OTTL mapping that turns those raw signals into a causal, engine-agnostic view in
SigNoz. This pre-event self-host was step zero — and it made the case for me.

*(Repo + full write-up coming in the main submission.)*
