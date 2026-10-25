"""Signing keys and the seal token printed in the QR code.

Token format:  MCS1.<payload>.<signature>
  payload    base64url of zlib-compressed canonical JSON (sorted keys, no spaces)
  signature  base64url of the Ed25519 signature over the uncompressed JSON bytes
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import zlib
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

PREFIX = "MCS1"


class TokenError(ValueError):
    """The text in a QR code is not a MedCore seal token."""


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def new_private_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def private_pem(key: Ed25519PrivateKey) -> bytes:
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())


def public_pem(key: Ed25519PrivateKey | Ed25519PublicKey) -> str:
    pub = key.public_key() if isinstance(key, Ed25519PrivateKey) else key
    return pub.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def load_public(pem: str) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(pem.encode())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("not an Ed25519 public key")
    return key


def fingerprint(public_key_pem: str) -> str:
    """A short, human-checkable ID for a public key, e.g. '3F9A 21C4 77B0 E15D'."""
    digest = hashlib.sha256(public_key_pem.encode()).hexdigest()[:16].upper()
    return " ".join(digest[i:i + 4] for i in range(0, 16, 4))


def sign_token(payload: dict, key: Ed25519PrivateKey) -> str:
    body = canonical(payload)
    return f"{PREFIX}.{_b64(zlib.compress(body, 9))}.{_b64(key.sign(body))}"


def parse_token(token: str) -> tuple[dict, bytes, bytes]:
    """Returns (payload, signed bytes, signature) without checking the signature."""
    parts = token.strip().split(".")
    if len(parts) != 3 or parts[0] != PREFIX:
        raise TokenError("not a MedCore seal")
    try:
        body = zlib.decompress(_unb64(parts[1]))
        payload = json.loads(body)
        signature = _unb64(parts[2])
    except (ValueError, zlib.error) as exc:
        raise TokenError("the seal is damaged and cannot be read") from exc
    if not isinstance(payload, dict) or payload.get("v") != 1:
        raise TokenError("unsupported seal version")
    return payload, body, signature


def signature_valid(public_key_pem: str, body: bytes, signature: bytes) -> bool:
    try:
        load_public(public_key_pem).verify(signature, body)
        return True
    except (InvalidSignature, ValueError):
        return False


def payload_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


class KeyStore:
    """Private keys on disk, one PEM per issuer. In a real install each hospital keeps
    only its own key, on its own machine; the server never needs it."""

    def __init__(self, *folders: Path):
        self.folders = [f for f in folders if f]

    def path(self, issuer_id: str) -> Path | None:
        for folder in self.folders:
            p = folder / f"{issuer_id}.pem"
            if p.exists():
                return p
        return None

    def load(self, issuer_id: str) -> Ed25519PrivateKey | None:
        p = self.path(issuer_id)
        if p is None:
            return None
        key = serialization.load_pem_private_key(p.read_bytes(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError(f"{p} is not an Ed25519 key")
        return key

    def save(self, issuer_id: str, key: Ed25519PrivateKey) -> Path:
        folder = self.folders[0]
        folder.mkdir(parents=True, exist_ok=True)
        p = folder / f"{issuer_id}.pem"
        p.write_bytes(private_pem(key))
        os.chmod(p, 0o600)
        return p
