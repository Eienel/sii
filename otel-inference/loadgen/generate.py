"""Load generator that deliberately produces a legible causal story.

It drives an OpenAI-compatible inference server (vLLM) through three phases so the
dashboard shows cause, not just symptom:

  1. WARM (low concurrency, shared-prefix prompts)
     -> high prefix-cache hit-rate, low queue wait. The "healthy" baseline.
  2. SPIKE (high concurrency, UNIQUE long prompts)
     -> cache hit-rate collapses (nothing shared) AND requests pile up in the
        scheduler queue. TTFT / e2e latency spike. This is the induced incident.
  3. RECOVER (back to shared-prefix, low concurrency)
     -> hit-rate climbs, queue drains, latency returns to baseline.

Run:
    python loadgen/generate.py --base-url http://localhost:8000 --model Qwen/Qwen2.5-0.5B-Instruct --ramp
"""

from __future__ import annotations

import argparse
import asyncio
import random
import time

import httpx

SHARED_PREFIX = (
    "You are a meticulous senior site-reliability engineer. Follow this incident "
    "runbook precisely and reason step by step. Runbook section 1: triage. "
    "Runbook section 2: correlate signals. Runbook section 3: mitigate. "
) * 4  # long, so prefix-cache hits are worth a lot

UNIQUE_TOPICS = [
    "quantum error correction", "medieval crop rotation", "tidal turbine bearings",
    "sourdough hydration ratios", "lunar regolith sintering", "coral spawning cycles",
    "railgun capacitor banks", "mycorrhizal nutrient trade", "airship ballast control",
]


def _shared_prompt() -> str:
    return SHARED_PREFIX + f" Now answer briefly: what is step {random.randint(1, 3)}?"


def _unique_prompt() -> str:
    topic = random.choice(UNIQUE_TOPICS)
    nonce = random.randint(10**9, 10**10)
    # unique nonce defeats prefix caching on purpose
    return f"[req-{nonce}] Explain {topic} in depth, covering {nonce} distinct aspects."


async def _one_request(client: httpx.AsyncClient, url: str, model: str, prompt: str) -> float:
    t0 = time.perf_counter()
    try:
        r = await client.post(
            url,
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 128,
                "temperature": 0.7,
            },
            timeout=120.0,
        )
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001 — load tool, we just record failures
        print(f"  ! request failed: {exc}")
        return -1.0
    return time.perf_counter() - t0


async def _phase(name: str, client, url, model, *, concurrency, duration_s, prompt_fn) -> None:
    print(f"\n=== phase {name}: concurrency={concurrency} for {duration_s}s ===")
    end = time.time() + duration_s
    latencies: list[float] = []

    async def worker() -> None:
        while time.time() < end:
            lat = await _one_request(client, url, model, prompt_fn())
            if lat >= 0:
                latencies.append(lat)

    await asyncio.gather(*[worker() for _ in range(concurrency)])
    if latencies:
        latencies.sort()
        p50 = latencies[len(latencies) // 2]
        p99 = latencies[min(len(latencies) - 1, int(len(latencies) * 0.99))]
        print(f"  {name}: n={len(latencies)} p50={p50:.2f}s p99={p99:.2f}s")


async def _run(args) -> None:
    url = args.base_url.rstrip("/") + "/v1/chat/completions"
    async with httpx.AsyncClient() as client:
        if args.ramp:
            await _phase("WARM", client, url, args.model,
                         concurrency=2, duration_s=args.phase_seconds, prompt_fn=_shared_prompt)
            await _phase("SPIKE", client, url, args.model,
                         concurrency=args.spike_concurrency, duration_s=args.phase_seconds,
                         prompt_fn=_unique_prompt)
            await _phase("RECOVER", client, url, args.model,
                         concurrency=2, duration_s=args.phase_seconds, prompt_fn=_shared_prompt)
        else:
            await _phase("STEADY", client, url, args.model,
                         concurrency=args.concurrency, duration_s=args.phase_seconds,
                         prompt_fn=_shared_prompt if args.shared_prefix else _unique_prompt)
    print("\ndone. inspect the causal dashboard in SigNoz.")


def main() -> None:
    p = argparse.ArgumentParser(description="causal load generator for self-hosted inference")
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    p.add_argument("--ramp", action="store_true", help="run WARM -> SPIKE -> RECOVER")
    p.add_argument("--phase-seconds", type=int, default=90)
    p.add_argument("--spike-concurrency", type=int, default=48)
    p.add_argument("--concurrency", type=int, default=8, help="for non-ramp steady mode")
    p.add_argument("--shared-prefix", action="store_true", help="steady mode: use shared-prefix prompts")
    args = p.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
