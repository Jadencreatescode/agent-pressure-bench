# Security Policy

## Supported versions

Security fixes are provided for the current 1.x release line.

## Reporting

Do not open a public issue for a suspected vulnerability that could expose credentials, private evaluation data, or host files. Use the repository host's private vulnerability-reporting feature when enabled, or contact the maintainers through the private address listed in the repository profile. Do not include live secrets; revoke them first.

Include the affected version, minimal reproduction, impact, and suggested mitigation. Maintainers will acknowledge a valid private report when operationally possible and coordinate disclosure after a fix.

## Threat model

Benchmark prompts, model responses, tool arguments, suite files, and persisted runs are untrusted. Relevant threats include path traversal, symlink escape, shell injection, oversized responses, malicious local HTTP endpoints, receipt/result tampering, credential leakage, and unintended execution outside a task workspace.

Controls in v1:

- strict suite admission before run-directory creation;
- relative-path and symlink traversal rejection;
- no host process or network execution tool in the core tool set;
- fail-closed optional `SandboxAdapter` integration for externally isolated executable actions;
- explicit per-task tool-call budgets and process timeout;
- externally anchored suite/admission SHA-256 plus bound result, verifier, workspace, route, and receipt digests;
- independent persisted-run verification with exact artifact and receipt reconciliation;
- API key read from a named environment variable, never a CLI value;
- synthetic public fixtures only.

## Operator responsibilities

Core filesystem checks confine its read/write/list operations but are not an OS sandbox. If an operator supplies a `SandboxAdapter`, run it in a disposable container or VM with a read-only base filesystem, limited task volume, no host credentials, no Docker socket, no cloud metadata access, network egress policy, and OS-level CPU/memory/process limits. Use a dedicated short-lived API credential. Model response text is not persisted by default, but run directories should still be treated as potentially sensitive metadata.

Do not expose the runner directly as a multi-tenant service. APB does not provide authentication, authorization, cryptographic run signatures, network isolation, or a hardened container boundary.

## Dependency and release policy

Runtime uses only the Python standard library. Development dependencies and GitHub Actions are reviewed before update. Release candidates must pass tests, clean-wheel install, all public fixture-suite smokes, archive safety checks, and candidate/staged-blob privacy scans. Publication and remote configuration are intentionally outside a local release gate.
