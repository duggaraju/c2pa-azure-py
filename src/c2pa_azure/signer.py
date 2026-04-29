from logging import getLogger
from typing import Self
from c2pa import Builder, Signer, load_settings
from io import BytesIO

from .trusted_signing import TrustedSigningClient, TrustedSigningSettings
from azure.core.credentials import TokenCredential
from cryptography.hazmat.primitives import hashes
from asn1crypto import cms, pem

logger = getLogger(__name__)

class AzureSigner:
    def __init__(self, credential: TokenCredential, settings: TrustedSigningSettings, manifest: str) -> None:
        load_settings(settings.c2pa_settings, "toml")
        self.builder = Builder(manifest)
        self.client = TrustedSigningClient(credential, settings)
        def sign(data:bytes) -> bytes:
            digest = hashes.Hash(hashes.SHA384())
            digest.update(data)
            return self.client.sign(digest.finalize())
        certs = self.client.get_certificate_chain()
        cert_chain_pem = AzureSigner.convert_p7b_to_pem(certs)
        self.signer = Signer.from_callback(sign, settings.algorithm, cert_chain_pem, "http://timestamp.acs.microsoft.com")

    @staticmethod
    def sort_certificates(certs: list) -> list:
        """Sort a certificate chain leaf -> root, excluding the root certificate.

        Expects `certs` to be a list of `asn1crypto.x509.Certificate` objects (typically
        from a CMS/PKCS#7 SignedData cert set).
        """

        if not certs:
            return []

        def subject_key(cert) -> bytes:
            return cert.subject.dump()

        def issuer_key(cert) -> bytes:
            return cert.issuer.dump()

        def is_root_certificate(cert) -> bool:
            # Treat a self-signed certificate that issues others in the set as the root.
            # (This matches typical Azure/PKCS#7 bundles which include the root CA.)
            return issuer_key(cert) == subject_key(cert) and subject_key(cert) in issuers_of_others

        by_subject: dict[bytes, object] = {}
        for cert in certs:
            by_subject.setdefault(subject_key(cert), cert)

        issuers_of_others = {
            issuer_key(cert)
            for cert in certs
            if issuer_key(cert) != subject_key(cert)
        }

        issuer_names = issuers_of_others

        leaf_candidates = [
            cert for cert in certs
            if subject_key(cert) not in issuer_names
        ]

        def build_chain(leaf_cert) -> list:
            chain: list = []
            current = leaf_cert
            seen_subjects: set[bytes] = set()

            while True:
                chain.append(current)
                sk = subject_key(current)
                if sk in seen_subjects:
                    break
                seen_subjects.add(sk)

                ik = issuer_key(current)
                if ik == sk:
                    break

                parent = by_subject.get(ik)
                if parent is None:
                    break

                current = parent

            return chain

        best_chain: list | None = None
        candidates = leaf_candidates if leaf_candidates else certs
        for candidate in candidates:
            chain = build_chain(candidate)
            if best_chain is None or len(chain) > len(best_chain):
                best_chain = chain

        assert best_chain is not None

        # Drop the root from the best chain (and from any extras) but keep all other certs.
        best_chain_no_root = [c for c in best_chain if not is_root_certificate(c)]

        best_subjects = {subject_key(c) for c in best_chain}
        remaining = [
            c
            for c in certs
            if subject_key(c) not in best_subjects and not is_root_certificate(c)
        ]

        sorted_chain = best_chain_no_root + remaining
        for cert in sorted_chain:
            try:
                logger.debug(
                    "Certificate: Subject: (%s) Issuer: (%s)",
                    cert.subject.human_friendly,
                    cert.issuer.human_friendly,
                )
            except Exception:
                logger.debug("Certificate: Subject/Issuer logging failed")

        return sorted_chain

    @staticmethod
    def convert_p7b_to_pem(p7b:bytes) -> bytes:
        # Azure may return either DER-encoded CMS or PEM-armored CMS.
        if pem.detect(p7b):
            _, _, der_bytes = pem.unarmor(p7b)
        else:
            der_bytes = p7b

        content_info = cms.ContentInfo.load(der_bytes)
        if content_info['content_type'].native != 'signed_data':
            raise ValueError(f"Unsupported CMS content_type: {content_info['content_type'].native}")

        signed_data = content_info['content']

        certs = []
        for cert_choice in signed_data['certificates']:
            # We only care about standard X.509 certificates here.
            if cert_choice.name == 'certificate':
                certs.append(cert_choice.chosen)

        certs = AzureSigner.sort_certificates(certs)
        buffer = BytesIO()
        for cert in certs:
            der = cert.dump()
            buffer.write(pem.armor('CERTIFICATE', der))

        buffer.seek(0)
        return buffer.getvalue()


    def sign(self: Self, input: str, output: str) -> None:
        self.builder.sign_file(input, output, self.signer)
