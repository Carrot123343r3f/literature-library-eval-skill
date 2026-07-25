"""Credential access for online sources; secrets never enter reports or manifests."""
import os


class CredentialError(RuntimeError):
    pass


def require_openalex_api_key():
    key = os.environ.get("OPENALEX_API_KEY", "").strip()
    if not key:
        raise CredentialError("OpenAlex requires a configured OPENALEX_API_KEY; no request was sent.")
    return key
