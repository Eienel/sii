# Alert · Queue wait p95 too high

**Intent:** fire when requests are spending too long waiting in the scheduler
before prefill — the earliest actionable sign of inference overload, ahead of the
user-visible latency SLO breach.

Create in SigNoz → **Alerts → New Alert → Metrics**.

- **Metric:** `gen_ai.server.queue.wait_duration`
- **Aggregation:** p95, time-aggregation `rate`
- **Group by:** `gen_ai.system`
- **Condition:** above `2` (seconds) for `5m`  ← tune to your SLO
- **Severity:** warning
- **Notification:** Slack / webhook

### Why this threshold placement works
Queue wait is a *leading* indicator: it rises before `gen_ai.server.request.duration`
because a request must finish waiting before its e2e latency is even recorded.
Alerting here buys you lead time to scale replicas or shed load.

### Builder query (for import / API)
```json
{
  "dataSource": "metrics",
  "aggregateAttribute": { "key": "gen_ai.server.queue.wait_duration", "type": "Histogram", "dataType": "float64" },
  "timeAggregation": "rate",
  "spaceAggregation": "p95",
  "groupBy": [{ "key": "gen_ai.system", "type": "tag", "dataType": "string" }],
  "op": ">", "target": 2, "matchType": "1", "evalWindow": "5m0s"
}
```
