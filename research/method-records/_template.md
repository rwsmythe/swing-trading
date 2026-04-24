<!--
Method record template — V2.1 §IV.B minimum viable fields.

Fields above the triple-dash are YAML frontmatter (parseable; don't add free-form
prose here). Fields below are Markdown (free-form).

`status` lifecycle per V2.1 §IV.B. Transitions require a changelog entry and a
new `version` value. Major version bumps (output semantics changes) require
source-of-truth correction protocol per V2.1 §VII.F.

Keep it short. This is the minimum viable record, not a dissertation.
-->

---
key: <stable-identifier-kebab-case>
name: <human-readable-name>
layer: <universe|ranking|trigger|sizing|stop|exit|regime|portfolio|operator-governance|monitoring>
status: <backlog|specified|prototype|validated|production|production_unvalidated|deprecated|retired|rejected>
baseline_or_predecessor: <method-key or "none" or description>
version: 0.1.0
last_updated: YYYY-MM-DD
---

# <Method name>

## Definition

<One paragraph: the deterministic logic/formula/rule that constitutes this method. Include inline citations to source material where the method has a source; use "internal" where the method originates in this project.>

## Inputs

<Bullet list: data fields / prior signals this method consumes. Note timing semantics where relevant (T-1 close vs. T-0 intraday, etc.).>

## Parameters

<Bullet list: named parameters with default values and valid ranges. If none, write "None.">

## Outputs

<Shape of output: scalar per ticker / ranked list / boolean flag / tuple. Units where applicable.>

## Operator explainability

- **One-sentence rationale:** <what the trader sees on the card>
- **One-paragraph explanation:** <what the trader sees when expanding>
- **FAQ:** <the most common operator objection and its answer>

## Validation notes

<Free text: what's been tested, what hasn't, known caveats, edge cases, regime dependencies, failure modes. As the method moves through statuses, this section grows.>

## Changelog

- YYYY-MM-DD — v0.1.0 — initial record.
