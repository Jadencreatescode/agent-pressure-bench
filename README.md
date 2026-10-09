# Agent Pressure Bench

Agent Pressure Bench (APB) is a model-neutral, synthetic benchmark for tool-using agents under bounded budgets, long-horizon pressure, failure edges, structured output, and related harness contracts.

**Release:** 1.0.0 · **Python:** 3.11+ · **License:** Apache-2.0

## Scope

The repository ships 11 runnable public suites describing 50 authored task concepts instantiated as 106 runnable fixtures/cells. The executable-coding portion contains 8 coding families with 3 substantively different variants each; repeated variants and context-budget cells are not claimed as independent task concepts. One separate public held-out-generator metadata document brings the public JSON document count to 12. The release also includes JSON schemas, a deterministic fixture adapter, an OpenAI-compatible HTTP adapter, tamper-evident receipts, and an independent verifier. It contains no hidden evaluation cases, model weights, private corpora, raw model transcripts, or credentials.

APB was inspired by public descriptions of pressure-oriented agent evaluation. It is not a reproduction of, exact parity with, or endorsed by Agent Max 2 or DFlash. See [METHODOLOGY.md](METHODOLOGY.md) and [NOTICE](NOTICE).

## Install

```sh
uv venv --python 3.11.15
uv pip install .
```

For development:

```sh
uv sync --extra dev --python 3.11.15
uv run pytest -q
```

No API key is needed for fixture runs. Wheels include the complete approved public fixture corpus, and all 11 public suites run in fixture mode without `APB_FIXTURE_ROOT` or a repository checkout. `APB_FIXTURE_ROOT` remains an optional development override. For transparency and reproducibility, the package includes fixture prompts, public inputs, manifests, verifiers/oracles, admission records, reference or known-good implementations and snapshots where present, and negative-control mutants; Python caches and generated build files are excluded. The fixture payload is about 1.4 MB uncompressed.

For a local or hosted OpenAI-compatible endpoint, copy `.env.example` values into your environment; never commit `.env`.

## CLI

```sh
apb list
apb run bounded --adapter fixture --output runs
apb verify runs/<run-id> --suite-digest <trusted-admission-sha256>
apb report results/agent-max-2-reference-aggregate.json --format json
```

OpenAI-compatible execution:

```sh
export APB_BASE_URL=https://api.example.com/v1
export APB_MODEL=example-model
export APB_API_KEY=replace-locally
apb run bounded --adapter openai --output runs
```

The adapter POSTs non-streaming requests to `<base-url>/chat/completions`. Core tools only read, write, and list paths under a per-task workspace; the core offers no host process or network execution tool. Executable tasks require an explicitly configured external `SandboxAdapter`. That adapter is a separate security boundary and must enforce container/VM filesystem, network, process, CPU, and memory policy; core path confinement is not container isolation.

## Public suites

`apb list` is authoritative. Fixture mode is a deterministic harness smoke test, not a model score. Every public suite has an explicit synthetic `fixture_response` so packaging, execution, persistence, and verification can be tested without provider access.

## Run artifacts

Each run directory contains:

- `suite.json`: exact admitted suite;
- `result.json`: task records and aggregate summary;
- `receipts.jsonl`: hash-linked event receipts;
- `manifest.json`: bindings for suite, verifier, result, workspace/mutation snapshot, route configuration, receipt head, and required artifact digests;
- `workspace/`: per-task files.

`apb verify` requires an externally retained suite/admission digest; it never treats a digest found inside the run as a trust anchor. It checks all manifest bindings, exact artifact enumeration, workspace hashes, result/check counts, task verdicts, and full receipt reconciliation. Hash chains detect modification relative to that external admission anchor; they do not provide signatures or prove who produced a run. Persisted model text is omitted by default; only hashes and the minimum structural evidence needed by the shipped evaluators are retained.

## Results and claims

The included `results/agent-max-2-reference-aggregate.json` is a sanitized aggregate reference supplied for this release. It is not an independently reproduced universal ranking. Different scoring treatments are kept separate, unavailable rates are `null`, and tool calls per second are never mislabeled as tokens per second.

## Documentation

- [Methodology](METHODOLOGY.md)
- [Security policy and threat model](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [Provenance manifest](PROVENANCE.json)
- [Release checklist](RELEASE_CHECKLIST.md)
- [Data and results reporting policy](REPORTING_POLICY.md)
- [Public/private hidden-suite architecture](HIDDEN_SUITE_ARCHITECTURE.md)
- [SBOM generation](docs/SBOM.md)
- [Static Pages landing page](docs/index.html)

## License and data

Code, schemas, documentation, synthetic suites, and repository-authored aggregate metadata are released under Apache-2.0 unless a file states otherwise. There are no bundled third-party datasets or media assets. See `NOTICE` and `PROVENANCE.json` for origin and redistribution details.
