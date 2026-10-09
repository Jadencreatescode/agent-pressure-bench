# SBOM Generation

Generate the release SBOM from the exact reviewed tree after installing from `uv.lock`:

```sh
uv sync --frozen --extra dev --python 3.11
uv run python scripts/generate_sbom.py --output artifacts/sbom.cdx.json
python -m json.tool artifacts/sbom.cdx.json >/dev/null
shasum -a 256 artifacts/sbom.cdx.json
```

The script emits deterministic CycloneDX 1.5 JSON for the application and all packages locked in `uv.lock`. It records the lockfile SHA-256 and labels the scope as the locked development/build environment. Runtime has no third-party Python dependencies. The fixed document serial number is intentional for reproducibility; release identity comes from the immutable Git commit, artifact digest, and evidence bundle rather than that field.

`artifacts/` is ignored because an SBOM must be generated from and bound to an immutable release candidate, reviewed with its dependency-license inventory, and attached to that release. Do not commit a stale working-tree SBOM. Record its SHA-256 in the private release evidence and publish it alongside the immutable release artifact.
