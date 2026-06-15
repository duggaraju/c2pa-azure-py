import argparse
import logging
import os
import sys
import traceback
from importlib.resources import files
from typing import Optional, Sequence

from azure.identity import DefaultAzureCredential
from c2pa import Builder, ContextBuilder, Settings

from .signer import AzureSigner
from .trusted_signing import TrustedSigningClient, TrustedSigningSettings


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="c2pa-azure-sign",
        description="Sign a file with a C2PA manifest using Azure Trusted Signing.",
    )
    parser.add_argument("-i", "--input", required=True, help="Path to the input file")
    parser.add_argument("-o", "--output", required=True, help="Path to the output file")
    parser.add_argument("-m", "--manifest", required=False, help="Path to the manifest file or inline manifest JSON")
    parser.add_argument("-f", "--force", action="store_true", default=True, help="Force overwrite of the output file")
    parser.add_argument("-s", "--settings", required=False, help="Path to the C2PA settings file (TOML)")
    group = parser.add_argument_group("Trusted Signing arguments")
    group.add_argument("-a", "--account", required=True, help="Trusted Signing service account")
    group.add_argument("-e", "--endpoint", required=True, help="Trusted Signing service endpoint")
    group.add_argument("-c", "--certificate-profile", required=True, help="Trusted Signing certificate profile")
    return parser


def _load_manifest(manifest_arg: Optional[str]) -> str:
    if manifest_arg:
        if os.path.exists(manifest_arg):
            with open(manifest_arg, "r") as f:
                return f.read()
        return manifest_arg
    return files("c2pa_azure.data").joinpath("manifest.json").read_text()


def _load_c2pa_settings(settings_arg: Optional[str]) -> str:
    if settings_arg and os.path.exists(settings_arg):
        with open(settings_arg, "r") as f:
            return f.read()
    return files("c2pa_azure.data").joinpath("settings.json").read_text()


def main(argv: Optional[Sequence[str]] = None) -> int:
    logging.basicConfig(level=logging.WARN)
    args = _build_parser().parse_args(argv)

    credential = DefaultAzureCredential()
    settings = TrustedSigningSettings(
        args.certificate_profile, args.account, args.endpoint)
    client = TrustedSigningClient(credential, settings)
    azure_signer = AzureSigner(client)
    signer = azure_signer.to_c2pa_signer()

    settings = Settings()
    c2pa_settings = _load_c2pa_settings(args.settings)
    settings.update(c2pa_settings)
    context = ContextBuilder().with_settings(settings).with_signer(signer).build()
    manifest = _load_manifest(args.manifest)
    builder = Builder(manifest, context)



    if args.force and os.path.exists(args.output):
        os.remove(args.output)
    builder.sign_file(args.input, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
