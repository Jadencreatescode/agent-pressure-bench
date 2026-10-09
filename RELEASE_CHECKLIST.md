# Release Checklist

This checklist is adapted from the local public benchmark release gate. It is fail-closed: an unchecked required item, scanner error, mutable reference, unclassified finding, or missing reviewer blocks publication. Keep sensitive evidence in an access-controlled evidence store; never put private paths, repository identifiers, canaries, credentials, hidden-suite versions, or session content in this public file.

## Candidate record

- Release version/tag: `<VERSION>` / `<TAG>`
- Public commit (40 hex): `<COMMIT>`
- Public archive SHA-256 (64 hex): `<DIGEST>`
- Reviewers: security `<NAME>`, privacy `<NAME>`, benchmark owner `<NAME>`
- UTC decision time: `<TIMESTAMP>`

## 1. Scope and boundary

- [ ] Build from an immutable clean commit, not a developer working tree.
- [ ] Inventory every candidate file; record count, bytes, largest files, binaries, archives, databases, and generated data privately.
- [ ] Confirm intentional Git ancestry and absence of nested repositories, submodules, inherited product history, or unexpected remotes.
- [ ] Confirm the public tree contains only approved harness code, schemas, synthetic fixtures, documentation, and aggregate results.
- [ ] Confirm hidden cases, scoring keys, canaries, raw transcripts, model weights, private corpora, credentials, and operational configuration are absent.

## 2. Candidate and staged-blob safety

- [ ] Verify `.gitignore` excludes secrets, local configuration, environments, caches, builds, run output, private evidence, databases, and archives.
- [ ] Enumerate tracked and intended untracked candidates using Git ignore rules.
- [ ] Reject unexpected modes, symlinks, submodules, case-colliding paths, oversized blobs, and unexplained binaries.
- [ ] Run two complementary secret scanners against candidate files and the exact staged blobs; record tool versions/configuration hashes and classify every match privately.
- [ ] Scan staged blobs for credentials, authenticated URLs, private keys, personal data, absolute user paths, internal hosts/addresses, infrastructure IDs, session content, and hidden canaries.
- [ ] Run `git diff --cached --check`; review the complete staged stat and binary diff; bind the approved manifest to the staged tree ID.

## 3. History and provenance

- [ ] Scan all reachable commits, tags, branches, notes, and LFS objects for secrets, private data, forbidden names, and oversized blobs.
- [ ] Rotate any exposed credential before rewriting/rebuilding history and rescanning.
- [ ] Validate `PROVENANCE.json`; verify rights, licenses, attribution, modifications, and redistribution basis for every public material.
- [ ] Confirm synthetic suite content is independently authored and no proprietary or leaked evaluation was copied.
- [ ] Validate `LICENSE`, `NOTICE`, `CITATION.cff`, and non-affiliation claims.
- [ ] Generate the CycloneDX SBOM using `docs/SBOM.md`; record its digest and dependency-license review privately.

## 4. Hidden-suite separation and results

- [ ] Review `HIDDEN_SUITE_ARCHITECTURE.md`; hidden material is held in a separate private repository/artifact, not merely ignored.
- [ ] Prove fork pull requests receive no hidden credentials, private environments, privileged triggers, or self-hosted runners.
- [ ] Scan source, packages, Pages, logs, caches, annotations, reports, and release artifacts for private canaries.
- [ ] Validate published data against `REPORTING_POLICY.md`; suppress small cells and strip prompts, responses, paths, IDs, exact timestamps, provider metadata, and infrastructure details.
- [ ] Independently recompute every aggregate from the private canonical ledger and review all claims, failures, exclusions, and uncertainty.

## 5. Build and artifact verification

- [ ] Install strictly from `uv.lock` in a new isolated clone and run `uv run pytest -q`.
- [ ] Run `python scripts/validate_release_materials.py` before tests/builds create caches.
- [ ] Build and install the wheel in a clean environment; run CLI and every public fixture suite without private inputs.
- [ ] Create the source archive from the immutable Git tree and reject traversal, links, special files, unsafe modes, duplicate/case-colliding names, and unexpected executables.
- [ ] Record archive digest, member count, uncompressed bytes, and exact manifest; rescan final artifact bytes.
- [ ] Verify no build/test accesses files outside the clone or contacts undocumented/private hosts.

## 6. GitHub and Pages controls

- [ ] Replace all `OWNER` placeholders, including `CODEOWNERS`, citation metadata, security links, and issue templates.
- [ ] Review and pin every GitHub Action to a full immutable commit SHA; SHA-pinned CI actions are not proof that tag-pinned Pages actions were reviewed.
- [ ] Set default workflow permissions to read-only; grant Pages `pages:write` and `id-token:write` only to the deploy workflow/job.
- [ ] Require pull requests, independent approvals, stale-approval dismissal, latest-push approval, resolved conversations, and required checks; disable force pushes and deletion.
- [ ] Enable secret scanning/push protection, dependency graph/alerts/updates, private vulnerability reporting, and code scanning where available.
- [ ] Audit collaborators, apps, hooks, deploy keys, runners, environments, variables, secrets, Pages, packages, and bypass actors.
- [ ] Verify Pages contains only `docs/`, exposes no build metadata/private content, and matches the approved commit.
- [ ] Protect release tags and environments; use immutable artifacts and a documented revocation path.

## 7. Remote read-back and approval

- [ ] Read back repository visibility, owner/name, default branch, rulesets, Actions permissions, security features, Pages source, and access configuration via UI/API.
- [ ] Confirm local commit, remote default-branch commit, release tag, and archive source commit all match.
- [ ] Enumerate and rescan the complete remote tree/history and downloaded release artifacts.
- [ ] Test logged-out public visibility and inspect Actions logs, annotations, caches, packages, releases, and Pages for excluded material.
- [ ] Obtain independent security, privacy, and benchmark-owner approval bound to the exact commit and archive digest.

## Final decision

```text
RELEASE VERDICT: PASS | FAIL | BLOCKED
PUBLIC COMMIT: <40-hex SHA>
PUBLIC ARCHIVE SHA256: <64-hex digest>
CANDIDATE / STAGED / HISTORY SCANS: PASS | FAIL
PRIVACY AND PATH SCAN: PASS | FAIL
LICENSE / PROVENANCE / SBOM: PASS | FAIL
HIDDEN-SUITE SEPARATION: PASS | FAIL
FRESH-CLONE PROOF: PASS | FAIL
GITHUB AND PAGES READ-BACK: PASS | FAIL
BASELINE REPORT REVIEW: PASS | FAIL
APPROVERS: <security>, <privacy>, <benchmark owner>
```

If private material leaks after publication: disable affected downloads/Pages, revoke credentials, preserve private incident evidence, rotate hidden cases/canaries, invalidate affected scores, clean history when necessary, and publish a disclosure without repeating sensitive content.
