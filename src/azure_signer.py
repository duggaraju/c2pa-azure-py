from logging import getLogger
from c2pa import Builder, create_signer
from io import BytesIO

from trusted_signing import TrustedSigningClient, TrustedSigningSettings
from azure.core.credentials import TokenCredential
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7

logger = getLogger(__name__)

class AzureSigner:
    def __init__(self, credential: TokenCredential, settings: TrustedSigningSettings, manifest: str):
        self.builder = Builder(manifest)
        self.client = TrustedSigningClient(credential, settings)
        def sign(data:bytes) -> bytes:
            digest = hashes.Hash(hashes.SHA384())
            digest.update(data)
            return self.client.sign(digest.finalize())
        certs = self.client.get_certificate_chain()
        pem = AzureSigner.convert_p7b_to_pem(certs)
        self.signer = create_signer(sign, settings.algorithm, pem, "http://timestamp.acs.microsoft.com")
    
    @staticmethod
    def sort_certificates(certs:list):
        sorted_certs = []
        for cert in certs:
            logger.debug(f"Certificate: Subject: ({cert.subject}) Isser: ({cert.issuer})")
            if cert.issuer == cert.subject:
                sorted_certs.insert(0, cert)
                continue
            else:
                index = next((i for i, c in enumerate(sorted_certs) if c.issuer == cert.subject), None)
                if index is None:
                    sorted_certs.append(cert)
                else:
                    sorted_certs.insert(index, cert)
        sorted_certs.reverse()
        return sorted_certs

    @staticmethod
    def convert_p7b_to_pem(p7b:bytes) -> bytes:
        buffer = BytesIO()
        certs = pkcs7.load_der_pkcs7_certificates(p7b)
        sorted_certs = AzureSigner.sort_certificates(certs)
        for cert in sorted_certs:
            logger.warning(f"Sorted Certificate: Subject = ({cert.subject}) Issuer= ({cert.issuer})")
            pem = cert.public_bytes(encoding=serialization.Encoding.PEM)
            buffer.write(pem)

        buffer.seek(0)
        return buffer.getvalue()


    def sign(self, input, output):
        self.builder.sign_file(self.signer, input, output)
