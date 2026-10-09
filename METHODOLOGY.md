# Methodology

## Design goals

APB measures whether a tool-using agent can complete synthetic, auditable tasks under explicit pressure constraints. It favors reproducible task state and independently recomputable outcomes over subjective judging.

## Corpus

Version 1 contains 50 independently authored synthetic task concepts instantiated as 106 runnable public fixtures/cells in 11 suites. This includes 8 executable-coding families with 3 substantively different variants per family. Variant and context-budget cells are distinct runnable fixtures, not independently authored task concepts. A separate held-out-generator metadata document makes 12 public JSON documents but is not runnable. Materials were reviewed for credentials, personal data, private paths, and restricted source material. The public held-out generator document explains deterministic mechanics but does not expose or reference any private suite. No hidden-suite identifier is required by the public harness.

Each suite declares schema version, stable ID, track, description, license, and tasks. Each task declares a unique ID, family, positive difficulty, prompt, non-negative tool-call budget, verifier, and optional public fixture response. Admission is fail-closed: unsupported versions, unknown fields, duplicate IDs, malformed budgets, unsafe verifier paths, or unknown verifiers are rejected before run state is created.

## Execution

A run receives exactly one suite. Each task starts with an isolated workspace and prompt. On every turn the adapter returns content and zero or more tool calls. Tool calls execute sequentially until a final response or the declared hard budget is reached. The runner records tool event receipts without prompt/output payloads. A task that exceeds its budget or never produces a final turn fails regardless of workspace state.

Available tools are UTF-8 file read/write, file listing, and argv-only process execution. Path traversal and symlink traversal are rejected. These are benchmark controls, not a substitute for an OS sandbox.

## Verification

Verifier types in v1 are:

- `final_equals`: exact final string equality;
- `file_equals`: exact UTF-8 file equality at a confined relative path;
- `json_schema`: parses the final response as JSON and requires named top-level keys.

The independent verifier checks file digests, validates the receipt hash chain, and recomputes each task verdict from the saved suite, final response, and workspace. The verifier intentionally does not trust the stored aggregate. SHA-256 receipts provide tamper evidence, not authenticity.

## Metrics

Primary published counts are passed, failed, and total tasks. Rates are `passed / total`, rounded to six decimal places by `apb report`. Tool calls per second and tokens per second are distinct fields; unavailable measurements are `null`. Fixture-mode success validates the harness and packaging only and must not be reported as model capability.

## Reproducibility and comparison

Publish the APB version, immutable source commit, suite ID, adapter/model label, endpoint implementation, sampling settings, run count, errors/timeouts, exclusions, and execution environment class. Run all predeclared rows, including failures. Do not merge rows with different scoring policies or imply universal rankings. Network latency and provider caching can materially affect throughput.

The bundled Agent Max 2 aggregate is supplied, sanitized reference metadata. APB does not claim reproduction, endorsement, exact DFlash parity, or direct comparability.

## Limitations

The public suites are synthetic and small; they do not establish production safety. Exact-match verifiers reward narrow outcomes. Fixture responses do not exercise model reasoning. `json_schema` is a required-key contract, not full JSON Schema evaluation. Hash receipts lack signatures. External endpoint behavior, token accounting, and hidden evaluations are outside the v1 public harness.
