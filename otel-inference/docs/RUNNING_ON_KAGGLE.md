# Running otel-inference on Kaggle (free T4)

The whole causal demo — vLLM, the convention collector, the GPU exporter, and the
load generator — runs inside one free Kaggle notebook exporting to SigNoz Cloud.
Budget ~15 minutes of wall-clock; it uses well under 1 of your 30 free GPU-hrs/week.

## Prerequisites (one-time, ~5 min)

**1. SigNoz Cloud account + ingestion key**
- Sign up at [signoz.io](https://signoz.io) → free trial → create a workspace.
- SigNoz UI → **Settings → Ingestion Settings**. Copy:
  - **Ingestion key** (UUID-looking string)
  - **Endpoint / region** — e.g. `ingest.us.signoz.cloud:443` (or `eu`/`in`). Keep the `:443`.

**2. Kaggle account**
- Sign up at [kaggle.com](https://kaggle.com), then **verify your phone number**
  (Settings → Phone Verification). Required to unlock GPU + internet in notebooks —
  without it the GPU option is greyed out.

## Step 1 — Create the notebook
- Kaggle → **Create → New Notebook**.
- **File → Import Notebook → GitHub**, paste:
  `https://github.com/Eienel/sii/blob/claude/signoz-hackathon-research-np9zyu/otel-inference/notebooks/kaggle_vllm.ipynb`
- Or create a blank notebook and paste the cells; the git-clone cell pulls the rest.

## Step 2 — Turn on GPU + Internet
Right-hand **Session options / Settings**:
- **Accelerator →** `GPU T4 x2` (T4 x1 is fine — the 0.5B model is tiny).
- **Internet →** `On` (needed for pip + reaching SigNoz Cloud).

## Step 3 — Add your SigNoz secrets
Right panel → **Add-ons → Secrets**. Add two, labels matching **exactly**:

| Label | Value |
|---|---|
| `SIGNOZ_CLOUD_ENDPOINT` | `ingest.us.signoz.cloud:443` (your region) |
| `SIGNOZ_INGESTION_KEY` | your key from prerequisites |

Cell 10 reads these via `UserSecretsClient()`.

## Step 4 — Run the setup cells (in order)
- **Cell 2 — Install** (~3–5 min): vLLM, OTel SDK, `nvidia-ml-py`, and the
  `otelcol-contrib` binary. Wait for a version to print.
- **Cell 4 — Clone repo** into `/kaggle/working/sii`.

## Step 5 — Kill-Probe A · do the metrics exist?
- **Cell 6**: boots vLLM (`Qwen2.5-0.5B-Instruct`, prefix caching + native traces),
  waits for `vLLM ready`, then prints `FOUND` / `MISSING` per metric.
- ✅ **all 10 print `FOUND`.**
- ❌ any `MISSING` → vLLM renamed something; it's a one-line fix in
  `collector/ottl/vllm.yaml`. First boot also downloads the model (~1–2 min).

## Step 6 — GPU exporter
- **Cell 8**: starts the pynvml→OTLP sidecar. Prints `gpu exporter started`.

## Step 7 — Kill-Probe B · can Kaggle reach SigNoz?
- **Cell 10**: loads secrets, runs `otelcol validate` (must pass), starts the
  collector, prints the tail of its log.
- ✅ log shows `Everything is ready. Begin running and processing data.` with no
  repeated `otlp/signoz_cloud` errors.
- ❌ `otlp/signoz_cloud` auth/connection errors → wrong endpoint or key.
  `otlp/signoz_local` errors are **expected/harmless** on Kaggle (no local SigNoz).

## Step 8 — Generate the incident
- **Cell 12**: load generator, `WARM → SPIKE → RECOVER` (~4.5 min). Prints p50/p99
  per phase; p99 should jump hard in SPIKE.

## Step 9 — See it in SigNoz
In SigNoz Cloud UI:
1. **Dashboards → New → Import JSON** → `dashboards/inference_causal.json`.
2. Time range **Last 15 min**, refresh.
3. Read top-to-bottom: symptom (`request.duration p99`, TTFT) → Cause A (queued /
   queue.wait) → Cause B (hit-rate collapse) → Cause C (prefill vs decode) →
   Hardware (GPU).
4. **Traces** → sort by duration → open a slow one → confirm high
   `gen_ai.latency.time_in_queue`.

## Step 10 — Teardown
- **Cell 14** terminates processes. Then **Stop Session** to save GPU quota.

## Common gotchas
- **GPU greyed out** → phone not verified.
- **Cell 6 hangs >5 min** → check `/kaggle/working/logs/vllm.log`; usually OOM →
  lower `--max-model-len` to `2048` in Cell 6.
- **No data in SigNoz** → time range too narrow, or wrong region endpoint; Cloud
  ingestion can lag ~30–60s.
- **Session ends at ~9–12h** → Kaggle hard limit; irrelevant for a ~10-min run.

## Feeding self-hosted SigNoz instead (for the pre-event blog)
Kaggle can't see your laptop directly. Expose your local SigNoz OTLP port with a
tunnel and point the collector's `otlp/signoz_local` exporter at it:
```bash
cloudflared tunnel --url tcp://localhost:4317
```
See [`../deploy/README.md`](../deploy/README.md).
