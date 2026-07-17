# Ollama adapter — the one-engine "primitive, not layer" proof

The claim otel-inference makes is that `gen_ai.server.*` is a **primitive** many
engines plug into, not a vLLM-specific **layer**. This adapter is the cheapest test
of that claim: populate the *same* convention (and therefore the *same* dashboard
and alerts) from a second, architecturally different engine — with zero dashboard
edits.

## What changes vs vLLM

Only the `where` clauses in the collector. See
[`../collector/ottl/ollama.yaml`](../collector/ottl/ollama.yaml). Nothing in
`dashboards/` or `alerts/` changes.

## Run it

```bash
# 1. serve any model with Ollama (exposes Prometheus /metrics on :11434)
OLLAMA_HOST=0.0.0.0 ollama serve
ollama run qwen2.5:0.5b "warm up"

# 2. point the collector's ollama scrape job at it (already in otelcol-config.yaml)
OLLAMA_METRICS_TARGET=127.0.0.1:11434 otelcol-contrib --config ../collector/otelcol-config.yaml

# 3. drive load (OpenAI-compatible endpoint on :11434/v1)
python ../loadgen/generate.py --base-url http://localhost:11434 --model qwen2.5:0.5b --ramp
```

## What you should see — and what you should NOT

| Convention metric | vLLM | Ollama | Reading |
|---|---|---|---|
| `gen_ai.server.request.duration` | ✅ | ✅ | symptom row works on both |
| `gen_ai.server.requests.running` | ✅ | ✅ | scheduler depth on both |
| `gen_ai.server.kv_cache.hit_rate` | ✅ | ⬜ **empty** | Ollama doesn't expose prefix-cache counters |
| `gen_ai.server.prefill.duration` | ✅ | ⬜ **empty** | Ollama doesn't split prefill/decode |
| `gen_ai.server.gpu.*` | ✅ | ✅ | same pynvml sidecar, engine-independent |

**The empty cells are the point.** A shared convention surfaces *engine capability
gaps* through one consistent lens. With per-engine dashboards you'd never notice
that Ollama simply cannot answer "was this slow request a cache miss?" — you'd just
have two dashboards that look superficially similar and mean different things.

## Honest scope

This is a **stub**, not a hardened Ollama integration. It exists to falsify the
"it's just a vLLM layer" objection in a day, not to ship production Ollama support.
The next engine (TGI, SGLang) is the same move: add a `where` block, add a row to
the coverage table.
