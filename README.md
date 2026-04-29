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
from c2pa_azure import AzureSigner, TrustedSigningSettings

credential = DefaultAzureCredential()

settings = TrustedSigningSettings(
    certificate_profile="my-cert-profile",
    service_account="my-trusted-signing-account",
    endpoint="https://eus.codesigning.azure.net/",
    # Optional: TOML-formatted C2PA settings string. None = library defaults.
    c2pa_settings=None,
)

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

signer = AzureSigner(credential, settings, manifest)
signer.sign("input.jpg", "output.jpg")
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

cert_chain_p7b = client.get_certificate_chain()
signature = client.sign(b"<sha384 digest bytes>")
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
└── data/                # bundled manifest.json and settings.toml
```

## Development

```sh
pip install -e ".[dev]"
pytest
python -m build           # produces dist/*.whl and dist/*.tar.gz
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
