# Contributing

By contributing, you agree that your contribution may be distributed under Apache-2.0 and that you have the right to submit it.

## Development

```sh
uv sync --extra dev --python 3.11.15
uv run pytest -q
```

Use strict test-driven development for behavior changes: add one failing behavioral test, observe the expected failure, implement the minimum fix, run the focused test, then the full suite. Keep runtime dependencies at zero unless a documented need outweighs the supply-chain cost.

## Suite changes

Suites must be synthetic, independently authored, deterministic where practical, and valid under schema/admission checks. Use obvious reserved examples (`example.com`, `203.0.113.0/24`) rather than real identities or infrastructure. Do not contribute proprietary prompts, hidden evaluations, model transcripts, personal data, copyrighted datasets, credentials, or private paths. Update both the canonical `suites/` file and its byte-identical packaged copy under `src/agent_pressure_bench/suites/`; tests enforce equality.

Document origin, license, acquisition date, modifications, and redistribution basis in `PROVENANCE.json`. Never disclose private hidden-suite identifiers or canaries.

## Pull requests

Keep changes scoped. Explain behavior and threat-model impact. Include tests, documentation, and provenance updates. Run the release checklist sections relevant to the change. Generated caches, run outputs, build products, local environments, and `.env` files must not be committed.

All contributions must follow `CODE_OF_CONDUCT.md`. Report security issues privately as described in `SECURITY.md`.
