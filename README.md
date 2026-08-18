# c2pa-azure-py

Sign files with [C2PA](https://c2pa.org) content credentials using the
[Azure Trusted Signing](https://learn.microsoft.com/azure/trusted-signing/) service.

The project ships in two forms from a single codebase:

- A **Python library** (`c2pa_azure`) you can import in your own apps.
- A **standalone CLI** (`c2pa-azure-sign`) you can run from the shell or a container.

## Installation

### From source

```sh
git clone https://github.com/duggaraju/c2pa-azure-py.git
cd c2pa-azure-py
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install .                        # add -e for an editable/dev install
```

### As a dependency in another project

```sh
pip install c2pa-azure                # once published to PyPI
# or directly from a Git ref:
pip install git+https://github.com/duggaraju/c2pa-azure-py.git
```

## Authentication

Sign in to Azure before running. Any credential supported by
[`DefaultAzureCredential`](https://learn.microsoft.com/python/api/azure-identity/azure.identity.defaultazurecredential)
will work (Azure CLI, Managed Identity, environment variables, etc.).

```sh
az login
# In WSL or headless environments:
az login --use-device-code
```

## CLI usage

```sh
c2pa-azure-sign \
    -i path/to/input.jpg \
    -o path/to/output.jpg \
    -e https://<region>.codesigning.azure.net/ \
    -a <trusted-signing-account> \
    -c <certificate-profile>
```

Equivalent invocation without an entry-point script:

```sh
python -m c2pa_azure -i input.jpg -o output.jpg -e https://... -a acct -c profile
```

Optional flags:

| Flag | Description |
| ---- | ----------- |
| `-m`, `--manifest` | Path to a manifest JSON file, or an inline manifest string. Defaults to the bundled [manifest.json](src/c2pa_azure/data/manifest.json). |
| `-s`, `--settings` | Path to a C2PA settings TOML file. |
| `-f`, `--force`    | Overwrite the output file if it already exists (default: on). |

## Library usage

```python
from azure.identity import DefaultAzureCredential
from c2pa import Builder, ContextBuilder
from c2pa_azure import AzureSigner, TrustedSigningClient, TrustedSigningSettings

credential = DefaultAzureCredential()

settings = TrustedSigningSettings(
    certificate_profile="my-cert-profile",
    service_account="my-trusted-signing-account",
    endpoint="https://eus.codesigning.azure.net/",
)
client = TrustedSigningClient(credential, settings)
azure_signer = AzureSigner(client)
signer = azure_signer.to_c2pa_signer()

manifest = """
{
  "claim_generator": "my_app/1.0.0",
  "title": "My Signed Image",
  "assertions": [
    { "label": "stds.schema-org.CreativeWork",
      "data": { "@context": "https://schema.org", "@type": "CreativeWork",
                "author": [{ "@type": "Person", "name": "Jane Doe" }] } }
  ]
}
"""
context = ContextBuilder().with_signer(signer).build()

builder = Builder(manifest, context)
builder.sign_file("input.jpg", "output.jpg")
```

### Loading the bundled manifest

```python
from importlib.resources import files
from c2pa_azure import AzureSigner, TrustedSigningSettings

manifest = files("c2pa_azure.data").joinpath("manifest.json").read_text()
```

### Calling the low-level Trusted Signing client

```python
from azure.identity import DefaultAzureCredential
from c2pa_azure import TrustedSigningClient, TrustedSigningSettings

settings = TrustedSigningSettings(
    "profile", "account", "https://eus.codesigning.azure.net/"
)
client = TrustedSigningClient(DefaultAzureCredential(), settings)
azure_signer = AzureSigner(client)

cert_chain_p7b = client.get_certificate_chain()
signature = azure_signer(b"<data to hash and sign>")
```

### Invoking the CLI from Python

```python
from c2pa_azure.cli import main

exit_code = main([
    "-i", "input.jpg",
    "-o", "output.jpg",
    "-e", "https://eus.codesigning.azure.net/",
    "-a", "my-account",
    "-c", "my-cert-profile",
])
```

## Docker

```sh
docker build -t c2pa-azure .
docker run --rm \
    -v "$PWD:/data" \
    -e AZURE_CLIENT_ID -e AZURE_TENANT_ID -e AZURE_CLIENT_SECRET \
    c2pa-azure \
    -i /data/input.jpg -o /data/output.jpg \
    -e https://<region>.codesigning.azure.net/ \
    -a <account> -c <certificate-profile>
```

## Project layout

```
src/c2pa_azure/
├── __init__.py          # public API: AzureSigner, TrustedSigningClient, TrustedSigningSettings
├── __main__.py          # enables `python -m c2pa_azure`
├── cli.py               # argparse entry point (c2pa-azure-sign)
├── signer.py            # AzureSigner
├── trusted_signing.py   # TrustedSigningClient + TrustedSigningSettings
└── data/                # bundled manifest.json and settings.json
```

## Development

```sh
pip install -e ".[dev]"
pytest
python -m build           # produces dist/*.whl and dist/*.tar.gz
```

### Load local module in editable mode (debugging)

When debugging changes in `src/c2pa_azure`, install this repo in editable mode so imports resolve to your local source tree:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -c "import c2pa_azure; print(c2pa_azure.__file__)"
```

The printed path should point to this checkout (not a site-packages wheel install).

### Release a new Python package version

1. Update the version in `pyproject.toml` and `src/c2pa_azure/__init__.py`.
2. Merge the change into `master` and confirm the Build workflow succeeds.
3. Create and publish a GitHub Release with a matching tag, such as `v0.37.7`.

The Release workflow verifies that the tag and both package version declarations
match, builds and validates the distributions, and publishes them to PyPI using
trusted publishing. Configure a PyPI trusted publisher for the `pypi` GitHub
environment before publishing the first release.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
