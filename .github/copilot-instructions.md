# Copilot instructions for `c2pa-azure-py`

## Build, test, and lint

Use a local virtual environment and install dev extras first:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Core commands:

```sh
ruff check .
pytest
python -m build
```

Run a single pytest test (node id form):

```sh
pytest tests/test_file.py::test_name -q
```

## High-level architecture

The codebase exposes both a library API and a CLI from the same core modules:

1. `c2pa_azure.cli:main` parses args, loads C2PA settings/manifest (from user input or bundled package data), builds the C2PA `Builder`, then delegates signing to `AzureSigner`.
2. `AzureSigner` (`signer.py`) bridges `c2pa-python` and Azure Trusted Signing: it fetches the certificate chain, infers the C2PA signing algorithm from the leaf cert, maps that algorithm to a digest hash, and creates `Signer.from_callback(...)`.
3. `TrustedSigningClient` (`trusted_signing.py`) owns Azure REST calls via `azure-core` pipeline: `get_certificate_chain()` fetches PKCS#7 certs; `sign()` posts digest + algorithm, then polls operation status until success/failure.
4. `__main__.py` routes `python -m c2pa_azure` to the same CLI entrypoint as the `c2pa-azure-sign` console script.

## Key conventions in this repository

1. **Algorithm ownership is in `AzureSigner`**: `TrustedSigningSettings` does not initialize `algorithm`; `AzureSigner` sets `client.settings.algorithm` after leaf-certificate analysis, and `TrustedSigningClient.sign()` depends on that field.
2. **Certificate chain handling is leaf-first, root-excluded**: PKCS#7 cert sets are parsed and reordered in `AzureSigner.sort_certificates()`; self-signed root certificates are intentionally removed before building the PEM chain passed to `Signer.from_callback`.
3. **CLI manifest/settings loading supports file path or inline content**: `-m/--manifest` is treated as file path if it exists, otherwise as inline JSON string; when omitted, bundled `src/c2pa_azure/data/manifest.json` is used. Settings similarly fall back to packaged `settings.json`.
4. **Trusted Signing endpoint is expected in base-URL form**: request URLs are built by direct string concatenation with `settings.endpoint`, so callers should pass endpoints like `https://<region>.codesigning.azure.net/` (including trailing slash), matching README examples.
