import argparse
import logging
import os
import traceback
from azure.identity import DefaultAzureCredential

from trusted_signing import TrustedSigningSettings
from azure_signer import AzureSigner

logging.basicConfig(level=logging.WARNING)
DEFAULT_MANIFEST = {
    "claim_generator_info": [{
        "name": "python test",
        "version": "0.1"
    }],
    "title": "My Title",
    "assertions": [
    {
            "label": "c2pa.training-mining",
            "data": {
                "entries": {
                "c2pa.ai_generative_training": { "use": "notAllowed" },
                "c2pa.ai_inference": { "use": "notAllowed" },
                "c2pa.ai_training": { "use": "notAllowed" },
                "c2pa.data_mining": { "use": "notAllowed" }
                }
            }
        }
    ]
}

# Create an ArgumentParser object
parser = argparse.ArgumentParser(description='This script does something.')

# Add arguments
parser.add_argument('-i', '--input', required=True, help='Path to the input file')
parser.add_argument('-o', '--output', required=True, help='Path to the output file')
parser.add_argument('-m', '--manifest', required=False, help='Path to the manifest file')
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
    manifest = DEFAULT_MANIFEST    

# Access the parsed arguments
credential = DefaultAzureCredential()
settings = TrustedSigningSettings(args.certificate_profile, args.account, args.endpoint)
try:
    signer = AzureSigner(credential, settings, manifest)
    signer.sign(args.input, args.output)
except Exception as e:
    print(traceback.format_exc())
