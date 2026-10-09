# Public/Private Hidden-Suite Architecture

## Boundary

The public repository contains the harness, public synthetic suites, schemas, documentation, and approved aggregate results. Hidden inputs, expected outputs, scoring keys, judge prompts, canaries, exploit cases, future test plans, and canonical run ledgers belong in a separate access-controlled private repository and separate artifacts. An ignore rule is not a security boundary.

The public harness may depend only on a documented, versioned exchange schema. It must not contain or emit private repository locations, filenames, paths, branches, commits, object IDs, checksums, canaries, case counts, or revealing taxonomies. A public score identifies the public benchmark version while the private operator binds it to the hidden-suite version in private evidence.

## Evaluation flow

1. A protected private orchestrator checks out immutable public and hidden revisions.
2. It validates the hidden bundle against the exchange schema before execution.
3. A least-privilege worker receives one case at a time, not the hidden repository.
4. The benchmarked agent receives only the case content and approved tools. It cannot access runner credentials, source repositories, host files, the container runtime socket, cloud metadata, or private networks.
5. The worker returns a minimal structured result. Raw private artifacts remain private.
6. A separate aggregation step applies suppression and `REPORTING_POLICY.md` before any public artifact is produced.

## CI and credentials

Public pull-request workflows use no hidden-suite credential, secret-bearing environment, self-hosted runner, or privileged `pull_request_target` execution. Hidden evaluation runs only from a protected private context after review. Checkout credentials are short-lived, read-only, environment-scoped, never placed on command lines, and removed before model execution. Public CI caches, annotations, logs, coverage, and artifacts must contain no hidden input or expected output.

## Leakage detection and response

Seed unique private canaries and scan public source, packages, Pages output, release archives, aggregate reports, and logs before publication. Test fork pull requests for secret isolation. On suspected leakage, stop publication, disable affected artifacts, rotate credentials and cases/canaries, invalidate affected scores, preserve private evidence, and inspect Git history before any republish. Hidden material is never moved into public history after retirement.

## Audit evidence

Privately retain immutable public/hidden revision bindings, canary-scan reports, fork-PR isolation results, log/artifact leakage tests, aggregate recomputation, access review, and named approvals. Public documentation must not reveal the evidence bundle's location or access mechanism.
