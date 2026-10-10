"""Web Push (VAPID) key pair, in the formats pywebpush and the browser expect.

    python -m boond.vapid      prints the private key (store it in SSM) and the public key

private: base64url raw P-256 private value (pywebpush / py_vapid Vapid.from_string)
public:  base64url uncompressed point, 65 bytes (PushManager.subscribe applicationServerKey)
"""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def generate():
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_numbers().private_value.to_bytes(32, "big")
    public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return _b64(private), _b64(public)


if __name__ == "__main__":
    private_key, public_key = generate()
    print(f"VAPID_PRIVATE_KEY={private_key}")
    print(f"VAPID_PUBLIC_KEY={public_key}")
