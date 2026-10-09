# Data and Results Reporting Policy

## Public data boundary

This repository may publish independently authored synthetic suites, schemas, harness code, aggregate measurements, and synthetic examples. It must not publish hidden cases, raw prompts or responses from private evaluation, scratchpads, tool transcripts, per-case hidden results, credentials, private infrastructure metadata, personal data, or session/run identifiers.

## Required result metadata

Every published result must identify the public benchmark version or commit, harness version, model's stable public name, scoring treatment, sampling parameters, run count, date range, declared hardware class, failures/timeouts, exclusions, and uncertainty or variance when meaningful. Hardware descriptions must remain generic and omit hostnames, addresses, account identifiers, local paths, and private endpoints.

## Aggregation and privacy

Publish aggregate metrics only at a granularity that cannot reconstruct hidden cases or identify participants. Suppress small cells and any breakdown that could reveal private suite structure. Strip prompts, responses, paths, environment variables, exact timestamps, request/session IDs, provider account metadata, and network identifiers. `null` means unavailable; it must not be converted to zero. Different scoring treatments remain separate.

## Completeness and claims

Predeclare handling for errors, refusals, timeouts, and invalid output. Report every planned model/configuration row, including failures; do not cherry-pick. Distinguish measured values from interpretation and label results as measurements under stated conditions, not universal rankings. Do not claim reproduction, parity, or endorsement by another benchmark unless independently established.

## Review and corrections

A reviewer must recompute published aggregates from the private canonical ledger and compare all tables and figures before release. Public artifacts receive a privacy and claims review. Correct material errors with a versioned replacement and changelog; never silently replace a release artifact. If private material leaks, remove access where possible, rotate affected hidden cases or credentials, invalidate impacted scores, preserve private incident evidence, and publish a disclosure that does not repeat sensitive content.

## Public reference aggregate

`results/agent-max-2-reference-aggregate.json` is sanitized, aggregate-only supplied reference metadata. It is not an independently reproduced ranking. Its provenance and limitations are recorded in `PROVENANCE.json` and `NOTICE`.
