import argparse
import logging
import os
import traceback
from azure.identity import AzureCliCredential

from trusted_signing import TrustedSigningSettings
from azure_signer import AzureSigner

# Set the logging level
logging.basicConfig(level=logging.INFO)

# Create an ArgumentParser object
parser = argparse.ArgumentParser(description='This script does something.')

# Add arguments
parser.add_argument('-i', '--input', required=True, help='Path to the input file')
parser.add_argument('-o', '--output', required=True, help='Path to the output file')
parser.add_argument('-m', '--manifest', required=False, help='Path to the manifest file')
parser.add_argument('-f', '--force', required=False, help='Force overwrite', default=True)
parser.add_argument('-s', '--settings', required=False, help='Path to the C2PA settings file')
group = parser.add_argument_group('Trustedsigning arguments')
group.add_argument('-a', '--account', required=True, help='Trusted signing service account')
group.add_argument('-e', '--endpoint', required=True, help='Trusted signing service endpoint')
group.add_argument('-c', '--certificate-profile', required=True, help='Trusted signing certificate profile')


# Parse the arguments
args = parser.parse_args()

if args.manifest:
    if os.path.exists(args.manifest):
        with open(args.manifest, 'r') as f:
            manifest = f.read()
    else:
        manifest = args.manifest
else:
    manifest_file = os.path.join(os.path.dirname(__file__), "manifest.json")    
    with open(manifest_file, 'r') as f:
        manifest = f.read()

if args.settings and os.path.exists(args.settings):
    with open(args.settings, 'r') as f:
        c2pa_settings = f.read()
else:
    c2pa_settings = None

# Access the parsed arguments
credential = AzureCliCredential() # ManagedIdentityCredential()
settings = TrustedSigningSettings(args.certificate_profile, args.account, args.endpoint, c2pa_settings)
try:
    if args.force and os.path.exists(args.output):
        os.remove(args.output)
    signer = AzureSigner(credential, settings, manifest)
    signer.sign(args.input, args.output)
except Exception as e:
    print(traceback.format_exc())
