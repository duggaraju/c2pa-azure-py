"""C2PA signing for Azure Trusted Signing."""
from .signer import AzureSigner
from .trusted_signing import TrustedSigningClient, TrustedSigningSettings

__all__ = ["AzureSigner", "TrustedSigningClient", "TrustedSigningSettings"]
__version__ = "0.37.4"
