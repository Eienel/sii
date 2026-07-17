"""GPU metrics -> OTLP, emitted under the gen_ai.server.gpu.* convention.

vLLM's /metrics does not include device-level GPU utilization/memory/power, and the
OTel Collector's DCGM receiver needs a DCGM daemon that free notebooks (Kaggle/Colab)
won't run. This sidecar reads NVML directly with pynvml and pushes OTLP metrics to
the collector, so GPU saturation shows up on the same causal dashboard as the
engine's queue/cache state.

Usage:
    python gpu_exporter/gpu_otel.py --endpoint http://localhost:4317 --interval 2

Metrics emitted (per GPU, attribute gpu.index / gpu.name):
    gen_ai.server.gpu.utilization   (ratio 0..1)
    gen_ai.server.gpu.memory.used   (bytes)
    gen_ai.server.gpu.power.usage   (watts)
"""

from __future__ import annotations

import argparse
import time

import pynvml
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource


def _build_meter(endpoint: str, export_interval_ms: int, gen_ai_system: str):
    resource = Resource.create(
        {
            "service.name": "otel-inference-gpu",
            "gen_ai.system": gen_ai_system,
        }
    )
    exporter = OTLPMetricExporter(endpoint=endpoint, insecure=endpoint.startswith("http://"))
    reader = PeriodicExportingMetricReader(exporter, export_interval_millis=export_interval_ms)
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(provider)
    return metrics.get_meter("otel-inference.gpu")


def main() -> None:
    parser = argparse.ArgumentParser(description="pynvml -> OTLP GPU exporter")
    parser.add_argument("--endpoint", default="http://localhost:4317", help="OTLP gRPC endpoint")
    parser.add_argument("--interval", type=float, default=2.0, help="sample interval seconds")
    parser.add_argument("--gen-ai-system", default="vllm", help="engine label for the GPU host")
    args = parser.parse_args()

    pynvml.nvmlInit()
    device_count = pynvml.nvmlDeviceGetCount()
    handles = [pynvml.nvmlDeviceGetHandleByIndex(i) for i in range(device_count)]
    names = [_decode(pynvml.nvmlDeviceGetName(h)) for h in handles]
    print(f"[gpu_otel] {device_count} GPU(s): {names} -> {args.endpoint}")

    meter = _build_meter(args.endpoint, int(args.interval * 1000), args.gen_ai_system)

    # Observable (async) gauges: NVML is polled inside the callbacks at export time.
    def _attrs(i: int):
        return {"gpu.index": str(i), "gpu.name": names[i]}

    def util_cb(_options):
        for i, h in enumerate(handles):
            u = pynvml.nvmlDeviceGetUtilizationRates(h)
            yield metrics.Observation(u.gpu / 100.0, _attrs(i))

    def mem_cb(_options):
        for i, h in enumerate(handles):
            m = pynvml.nvmlDeviceGetMemoryInfo(h)
            yield metrics.Observation(float(m.used), _attrs(i))

    def power_cb(_options):
        for i, h in enumerate(handles):
            try:
                w = pynvml.nvmlDeviceGetPowerUsage(h) / 1000.0  # mW -> W
            except pynvml.NVMLError:
                w = 0.0
            yield metrics.Observation(w, _attrs(i))

    meter.create_observable_gauge(
        "gen_ai.server.gpu.utilization", callbacks=[util_cb], unit="1",
        description="GPU SM utilization (0..1)",
    )
    meter.create_observable_gauge(
        "gen_ai.server.gpu.memory.used", callbacks=[mem_cb], unit="By",
        description="GPU memory used in bytes",
    )
    meter.create_observable_gauge(
        "gen_ai.server.gpu.power.usage", callbacks=[power_cb], unit="W",
        description="GPU board power draw in watts",
    )

    try:
        while True:
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[gpu_otel] shutting down")
    finally:
        pynvml.nvmlShutdown()


def _decode(name) -> str:
    return name.decode() if isinstance(name, (bytes, bytearray)) else str(name)


if __name__ == "__main__":
    main()
