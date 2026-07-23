# AI Use Disclosure

*Required by the [Agents of SigNoz hackathon rules](https://www.wemakedevs.org/hackathons/signoz/rules):
"Use of AI assistants (ChatGPT, Copilot, etc.) is permitted but must be declared."*

## Summary

This project was built with substantial use of an AI coding assistant
(**Claude Code**, Anthropic). AI was used as a pair-programmer throughout; all
direction, idea selection, architecture decisions, and final review were done by
the human team member.

## What AI was used for

- **Research** — surveying vLLM's native OpenTelemetry support, the OTel GenAI
  semantic-conventions issue (#87), and prior art (Parseable, Dash0), to locate the
  unowned seam this project targets.
- **Idea pressure-testing** — running candidate directions through an
  idea-interrogation framework to pick the one that held up.
- **Authoring** — drafting the collector config and OTTL convention-mapping rules,
  the GPU exporter, the load generator, the candidate `gen_ai.server.*` convention
  spec, the Kaggle notebook, the dashboard/alert scaffolds, the landing page, and
  documentation.

## What the human did

- Chose the problem, the track fit, and the final idea.
- Owns all architecture and design decisions.
- Runs the workload on real hardware (Kaggle T4), verifies outputs, and rebuilds the
  dashboard against real ingested data (AI-authored dashboard JSON is a scaffold, not
  the final truthed artifact).
- Reviews and is accountable for everything submitted.

## Scope note

Dashboards, metric names, and alert thresholds authored by AI are treated as
**hypotheses pending runtime verification**, not finished work. The final submission
reflects what actually ingested into SigNoz on real hardware.
