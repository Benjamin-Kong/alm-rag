# Intranet model profile setup — TDD evidence

Scope: SRS-048 (exact tokenizer/context limits), SRS-051 (external model configuration), SRS-059 (real gate evidence). User requests intranet operational setup, with actual ALM/Ollama tests performed later on the Linux server. No actual model or ALM was contacted during this implementation.

## Red

Before `src/almrag/model_setup.py` existed, created `tests/test_model_setup.py` covering portable offline configuration, atomic nonoverwrite/explicit replacement, pinned artifact/digest/model/dimension rejection, explicit calibration, exact prompt-count/digest mismatch preservation, tokenizer/output alias rejection.

Command in isolated worktree:

```text
PYTHONPATH=src /Users/skongby/projects/alm-rag/.venv/bin/pytest -q tests/test_model_setup.py
```

Observed: exit 2; collection error `ModuleNotFoundError: No module named 'almrag.model_setup'`; 1 error in 0.24s. This is actual missing-module Red evidence, not a claimed behavioral failure against preexisting production code.

## Green / regression

Added offline-first `prepare_profile` and operator CLI; kept approved model-name restriction, existing tokenizer loader and runtime digest/context/vector/exact-count checks unchanged. Network is opt-in with `--verify`; test transport is explicitly FIXTURE_ONLY. Atomic exclusive publication uses private temporary file and link; explicit overwrite uses atomic replace after complete validation. Profiles contain LocalModelProfile fields only and cannot claim prior VERIFIED trust.

First run of new tests + existing embedding/runtime suite: **24 passed in 1.82s**. Added further negative credential, symlink/missing artifact, sanitized CLI failure and round-trip registry regression cases. Final run:

```text
PYTHONPATH=src /Users/skongby/projects/alm-rag/.venv/bin/pytest -q tests/test_model_setup.py tests/test_embedding.py tests/test_model_runtime.py
30 passed in 2.05s
```

All model requests used `httpx.MockTransport`; offline test forbids `httpx.Client.send`. CLI subprocess failure returns nonzero, prints only a stable error code and does not reveal filesystem paths. Hash/count/digest mismatch tests preserve an existing output byte-for-byte. Env token tests assert header resolution while excluding values from profile and evidence. No real tokenizers or customer data are committed.

## Status

- PASS: 30 local tests, including prior embedding/model-runtime regression.
- NOT VERIFIED: actual Linux operator installation, approved model availability, real tokenizer special-token equivalence, actual Ollama digest/dimension/count calibration, container artifact permissions/network, production throughput/search quality.
- No API/authentication/ACL policy or existing model restriction changed by this module. Root owns overall integration/QA/push decisions.

## Official Ollama identity-format compatibility correction

Official `/api/tags` response example (<https://docs.ollama.com/api/tags>) uses a bare model name and a raw 64-hex digest. Existing runtime required `:latest` and `sha256:` from the server and rejected the official formats. Added `tests/test_ollama_identity_formats.py` before changing `embedding.py`. Actual first Red: **5 failed, 12 passed in 0.21s**; raw digest/default name rejected, equivalent duplicate identities not classified as ambiguous. Expanded Red before implementation with vector-response canonical-name cases: **7 failed, 12 passed in 0.20s**. Existing explicit-tag code also incorrectly accepted an extra `:latest` suffix; test now rejects it.

Minimal correction canonicalizes a missing model tag to `:latest` and only raw lowercase 64-hex digests to the existing `sha256:` format. Digest pinning, approved ModelConfig name restriction, context checks, exact tokenizer count, model configuration values and fingerprint contracts remain unchanged. Multiple equivalent tag records fail closed as ambiguous. Different tags/digests, malformed/non-string digest values and extra tag suffixes fail closed. CLI continues to require canonical `sha256:` input; operator documentation explains raw tags conversion.

Regression command:

```text
PYTHONPATH=src /Users/skongby/projects/alm-rag/.venv/bin/pytest -q tests/test_ollama_identity_formats.py tests/test_model_setup.py tests/test_embedding.py tests/test_model_runtime.py
49 passed in 2.07s
```

PASS: local 49-test regression including 19 identity-format cases. NOT VERIFIED: actual Ollama on the target Linux server. No network model calls or model downloads were performed.
