# Self-hosted SigNoz (for the pre-event blog / data ownership)

The **canonical** way to self-host SigNoz is their maintained compose bundle — it
pins matching ClickHouse / query-service / collector / frontend versions, which
drift often enough that you should not hand-maintain them:

```bash
git clone -b main https://github.com/SigNoz/signoz.git
cd signoz/deploy/docker
docker compose up -d
# SigNoz UI: http://localhost:8080   (OTLP ingest: localhost:4317/4318)
```

`docker-compose.signoz.yaml` in this folder is a **thin convenience** for a
single-box demo; if it and the upstream bundle disagree, upstream wins.

## Pointing otel-inference at self-hosted SigNoz

SigNoz's own OTel collector listens on `4317` (gRPC) / `4318` (HTTP). Our
collector's `otlp/signoz_local` exporter already targets `127.0.0.1:4317`.

Two topologies:

- **Everything local** (single box with a GPU): run vLLM, our collector, and the
  SigNoz bundle on the same host. `otlp/signoz_local` → `127.0.0.1:4317`.
- **Compute on Kaggle, SigNoz on your laptop** (the realistic free-GPU case):
  expose your laptop's `4317` to the notebook with a tunnel:

  ```bash
  cloudflared tunnel --url tcp://localhost:4317
  # set the printed hostname as the collector's otlp/signoz_local endpoint,
  # or just use SIGNOZ_CLOUD_ENDPOINT for the notebook and self-host for a
  # captured-and-replayed run of the same data for the blog.
  ```

## Importing the dashboard & alerts

- Dashboard: SigNoz UI → **Dashboards → Import JSON** → `../dashboards/inference_causal.json`
- Alerts: **Alerts → New Alert**, or import the definitions in `../alerts/`.
