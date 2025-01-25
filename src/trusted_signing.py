import base64
import json
from logging import getLogger
from operator import itemgetter
from time import sleep
from azure.core.pipeline import Pipeline
from c2pa import SigningAlg

logger = getLogger(__name__)
from azure.core.credentials import (TokenCredential)
from azure.core.pipeline.policies import (
    BearerTokenCredentialPolicy,
    ContentDecodePolicy,
    DistributedTracingPolicy,
    HeadersPolicy,
    HttpLoggingPolicy,
    NetworkTraceLoggingPolicy,
    UserAgentPolicy,
    RetryPolicy,
)
from azure.core.rest import HttpRequest, HttpResponse
from azure.core.exceptions import AzureError
from azure.core.pipeline.transport import RequestsTransport

class TrustedSigningSettings(object):
    def __init__(self, certificate_profile, service_account, endpoint):
        self.certificate_profile = certificate_profile
        self.service_account = service_account
        self.endpoint = endpoint
        self.version = "2022-06-15-preview"
        self.algorithm = SigningAlg.PS384

class SigningRequest:
    def __init__(self, alg: str, digest: bytes):
        self.signatureAlgorithm = alg
        self.digest = base64.b64encode(digest).decode('utf-8')
    def __repr__(self) -> str:
        return json.dumps(self.__dict__)[:1024]
    
class TrustedSigningClient(object):

    def __init__(self, credential: TokenCredential, settings: TrustedSigningSettings, **kwargs):
        self.settings = settings
        self._pipeline = self._create_pipeline(credential, settings.endpoint, kwargs=kwargs)

    def _create_pipeline(self, credential: TokenCredential, base_url=None, **kwargs):
        transport = kwargs.get('transport') or RequestsTransport(**kwargs)

        try:
            policies = kwargs['policies']
        except KeyError:
            scope = "https://codesigning.azure.net/.default"
            if hasattr(credential, "get_token"):
                credential_policy = BearerTokenCredentialPolicy(credential, scope)
            else:
                raise ValueError(
                    "Please provide an instance from azure-identity or a class that implement the 'get_token protocol"
                )
            policies = [
                HeadersPolicy(**kwargs),
                UserAgentPolicy(**kwargs),
                ContentDecodePolicy(**kwargs),
                RetryPolicy(**kwargs),
                credential_policy,
                HttpLoggingPolicy(**kwargs),
                DistributedTracingPolicy(**kwargs),
                NetworkTraceLoggingPolicy(**kwargs)
            ]

        return Pipeline(transport, policies)
    
    def get_certificate_chain(self) -> bytes:
        url = f'{self.settings.endpoint}codesigningaccounts/{self.settings.service_account}/certificateprofiles/{self.settings.certificate_profile}/sign/certchain?api-version={self.settings.version}'
        request = HttpRequest("GET", url, headers = {"accept": "application/pkcs7-mime"})
        response = self._pipeline.run(request)
        p7b = response.http_response.read()
        return p7b    

    def sign(self, digest: bytes) -> bytes:
        url = f'{self.settings.endpoint}codesigningaccounts/{self.settings.service_account}/certificateprofiles/{self.settings.certificate_profile}/sign?api-version={self.settings.version}'
        json = { "digest": base64.b64encode(digest).decode('utf-8'), "signatureAlgorithm": self.settings.algorithm.name}
        request = HttpRequest("POST", url, json = json)
        response = self._pipeline.run(request)
        result = response.http_response.json()
        url = f'{self.settings.endpoint}codesigningaccounts/{self.settings.service_account}/certificateprofiles/{self.settings.certificate_profile}/sign/{result["operationId"]}?api-version={self.settings.version}'
        while result["status"] == 'InProgress':
            sleep(0.25)
            request = HttpRequest("GET", url)
            response = self._pipeline.run(request)
            result = response.http_response.json()
        
        if result["status"] == 'Succeeded':
            return base64.b64decode(result["signature"])

        raise AzureError(f"Signing failed: for operation Id: {result["operationId"]} Status: {result["status"]}")
