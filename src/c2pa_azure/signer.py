from logging import getLogger
from typing import Optional, Self
from c2pa import Signer, C2paSigningAlg
from io import BytesIO

from .trusted_signing import TrustedSigningClient
from cryptography.hazmat.primitives import hashes
from asn1crypto import cms, pem, x509

logger = getLogger(__name__)

# Hash algorithm to use when computing the digest sent to Trusted Signing,
# keyed by the C2PA signing algorithm derived from the leaf certificate.
_ALG_TO_HASH: dict[C2paSigningAlg, type[hashes.HashAlgorithm]] = {
    C2paSigningAlg.PS256: hashes.SHA256,
    C2paSigningAlg.PS384: hashes.SHA384,
    C2paSigningAlg.PS512: hashes.SHA512,
    C2paSigningAlg.ES256: hashes.SHA256,
    C2paSigningAlg.ES384: hashes.SHA384,
    C2paSigningAlg.ES512: hashes.SHA512,
}

class AzureSigner:
    def __init__(self, client: TrustedSigningClient, alg: Optional[C2paSigningAlg] = None) -> None:
        self.client = client
        p7b = self.client.get_certificate_chain()
        certs = AzureSigner._parse_p7b(p7b)
        sorted_certs = AzureSigner.sort_certificates(certs)
        if not sorted_certs:
            raise ValueError("Trusted Signing returned an empty certificate chain")

        leaf = sorted_certs[0]
        if alg is None:
            alg = AzureSigner.infer_signing_algorithm(leaf)
            logger.debug("Inferred C2PA signing algorithm from leaf certificate: %s", alg.name)

        # Override the placeholder algorithm in settings so the REST call to
        # Trusted Signing requests the matching signature algorithm.
        self.client.settings.algorithm = alg
        hash_cls = _ALG_TO_HASH[alg]

        def sign(data: bytes) -> bytes:
            digest = hashes.Hash(hash_cls())
            digest.update(data)
            return self.client.sign(digest.finalize())

        cert_chain_pem = AzureSigner._certs_to_pem(sorted_certs)
        self.signer = Signer.from_callback(sign, alg, cert_chain_pem, "http://timestamp.acs.microsoft.com")

    @staticmethod
    def infer_signing_algorithm(leaf: x509.Certificate) -> C2paSigningAlg:
        """Derive the C2PA signing algorithm from a leaf X.509 certificate.

        Trusted Signing uses RSA-PSS for RSA keys and ECDSA for EC keys; the
        hash size is paired with the key size / curve per RFC 8152 / COSE.
        """
        public_key = leaf.public_key
        alg = public_key.algorithm  # 'rsa' | 'rsassa_pss' | 'ec' | 'dsa'

        if alg in ("rsa", "rsassa_pss"):
            bit_size = public_key.bit_size
            if bit_size <= 2048:
                return C2paSigningAlg.PS256
            if bit_size <= 3072:
                return C2paSigningAlg.PS384
            return C2paSigningAlg.PS512

        if alg == "ec":
            curve_type, curve_name = public_key.curve
            # asn1crypto returns OID-derived names like 'secp256r1', 'secp384r1', 'secp521r1'.
            ec_map = {
                "secp256r1": C2paSigningAlg.ES256,
                "prime256v1": C2paSigningAlg.ES256,
                "secp384r1": C2paSigningAlg.ES384,
                "secp521r1": C2paSigningAlg.ES512,
            }
            if curve_name not in ec_map:
                raise ValueError(f"Unsupported EC curve in leaf certificate: {curve_name}")
            return ec_map[curve_name]

        raise ValueError(f"Unsupported public key algorithm in leaf certificate: {alg}")

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
    def _parse_p7b(p7b: bytes) -> list:
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
        return certs

    @staticmethod
    def _certs_to_pem(certs: list) -> bytes:
        buffer = BytesIO()
        for cert in certs:
            buffer.write(pem.armor('CERTIFICATE', cert.dump()))
        buffer.seek(0)
        return buffer.getvalue()

    @staticmethod
    def convert_p7b_to_pem(p7b: bytes) -> bytes:
        certs = AzureSigner.sort_certificates(AzureSigner._parse_p7b(p7b))
        return AzureSigner._certs_to_pem(certs)
