# Alert · Prefix-cache hit-rate collapse

**Intent:** fire when the prefix-cache hit-rate drops sharply, because every cache
miss becomes prefill compute — the dominant, silent driver of TTFT regressions in
self-hosted inference. Latency dashboards show the *symptom*; this alert names the
*cause* before someone pages you.

Create in SigNoz → **Alerts → New Alert → Metrics**, using a formula.

- **Query A:** `gen_ai.server.kv_cache.hits`, time-agg `rate`, space-agg `sum` (disabled from view)
- **Query B:** `gen_ai.server.kv_cache.queries`, time-agg `rate`, space-agg `sum` (disabled from view)
- **Formula F1:** `A / B`  → hit-rate (0..1)
- **Condition:** below `0.3` for `10m`  ← tune to your workload's shared-prefix ratio
- **Severity:** warning
- **Notification:** Slack / webhook

### Why a formula, not a stored metric
`hits` and `queries` are token-granularity counters. The only correct rolling
hit-rate is `rate(hits) / rate(queries)`; a precomputed gauge would be wrong across
scrape boundaries. See `convention/gen_ai_server_conventions.md`.

### Caveat
Only meaningful for engines that expose prefix-cache counters (vLLM ✅, Ollama ⬜).
For engines without them the formula yields no data — which the coverage table in
the convention doc already documents.
