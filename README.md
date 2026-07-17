# sii

**[`otel-inference/`](otel-inference/)** — OpenTelemetry-native *causal* observability
for self-hosted LLM inference, built for the
[Agents of SigNoz](https://www.wemakedevs.org/hackathons/signoz) hackathon.

vLLM already emits the signals; nobody has agreed on their *names*, so you can't
build one dashboard that explains **why** a self-hosted LLM is slow — or reuse it on
the next engine. This repo defines a candidate `gen_ai.server.*` semantic convention
(mirroring [semantic-conventions-genai#87](https://github.com/open-telemetry/semantic-conventions-genai/issues/87)),
maps each engine's raw metrics into it with an OTTL ruleset, and ships a causal
SigNoz dashboard that decomposes a latency spike into its cause.

- **Start here:** [`otel-inference/README.md`](otel-inference/README.md)
- **Run it on a free GPU:** [`otel-inference/docs/RUNNING_ON_KAGGLE.md`](otel-inference/docs/RUNNING_ON_KAGGLE.md)
- **The convention:** [`otel-inference/convention/gen_ai_server_conventions.md`](otel-inference/convention/gen_ai_server_conventions.md)
