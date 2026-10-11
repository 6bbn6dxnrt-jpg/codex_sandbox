"""Streaming authenticated encryption; only the public key is used remotely."""
from __future__ import annotations
import base64
import hashlib
import json
import os
import struct
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MAGIC = b"LWEALTH1\n"
CHUNK = 1024 * 1024
MAX_HEADER = 16384

def public_fingerprint(public_bytes: bytes) -> str:
    public = serialization.load_pem_public_key(public_bytes)
    der = public.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(der).hexdigest()

def generate_keypair(private_path: Path, public_path: Path) -> str:
    if private_path.exists() or public_path.exists():
        raise FileExistsError("Refusing to replace existing encryption keys")
    private = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    private_bytes = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    public_bytes = private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(private_bytes)
    public_path.write_bytes(public_bytes)
    return public_fingerprint(public_bytes)

def seal_file(source: Path, target: Path, public_path: Path) -> dict:
    public_bytes = public_path.read_bytes()
    public = serialization.load_pem_public_key(public_bytes)
    if not isinstance(public, rsa.RSAPublicKey) or public.key_size < 3072:
        raise ValueError("RSA key must be at least 3072 bits")
    key = os.urandom(32)
    nonce = os.urandom(12)
    wrapped = public.encrypt(key, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=MAGIC))
    header = json.dumps({"version": 1, "algorithm": "AES-256-GCM+RSA-OAEP-SHA256", "recipient": public_fingerprint(public_bytes), "nonce": base64.b64encode(nonce).decode(), "wrapped_key": base64.b64encode(wrapped).decode()}, sort_keys=True, separators=(",", ":")).encode()
    prefix = MAGIC + struct.pack(">I", len(header)) + header
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(prefix)
    partial = target.with_suffix(target.suffix + ".partial")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with source.open("rb") as src, partial.open("xb") as out:
            out.write(prefix)
            for chunk in iter(lambda: src.read(CHUNK), b""):
                out.write(encryptor.update(chunk))
            out.write(encryptor.finalize())
            out.write(encryptor.tag)
        os.replace(partial, target)
    finally:
        partial.unlink(missing_ok=True)
    return inspect_envelope(target)

def inspect_envelope(path: Path) -> dict:
    with path.open("rb") as src:
        magic = src.read(len(MAGIC))
        if magic != MAGIC:
            raise ValueError("Invalid envelope magic")
        length_bytes = src.read(4)
        if len(length_bytes) != 4:
            raise ValueError("Truncated envelope")
        length = struct.unpack(">I", length_bytes)[0]
        if not 0 < length <= MAX_HEADER:
            raise ValueError("Invalid envelope header length")
        header_bytes = src.read(length)
        header = json.loads(header_bytes)
        if header.get("version") != 1 or header.get("algorithm") != "AES-256-GCM+RSA-OAEP-SHA256":
            raise ValueError("Unsupported envelope")
        if path.stat().st_size <= len(MAGIC) + 4 + length + 16:
            raise ValueError("Missing ciphertext")
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(CHUNK), b""):
            digest.update(chunk)
    return {"recipient": header["recipient"], "encrypted_bytes": path.stat().st_size, "ciphertext_sha256": digest.hexdigest()}

def open_file(source: Path, target: Path, private_path: Path) -> dict:
    if target.exists():
        raise FileExistsError("Refusing to replace decrypted output")
    private = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    with source.open("rb") as src:
        if src.read(len(MAGIC)) != MAGIC:
            raise ValueError("Invalid envelope")
        length_bytes = src.read(4)
        if len(length_bytes) != 4:
            raise ValueError("Truncated envelope")
        length = struct.unpack(">I", length_bytes)[0]
        if not 0 < length <= MAX_HEADER:
            raise ValueError("Invalid envelope header length")
        header_bytes = src.read(length)
        header = json.loads(header_bytes)
        expected = public_fingerprint(private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        if header.get("recipient") != expected or header.get("algorithm") != "AES-256-GCM+RSA-OAEP-SHA256" or header.get("version") != 1:
            raise ValueError("Wrong recipient or unsupported envelope")
        key = private.decrypt(base64.b64decode(header["wrapped_key"], validate=True), padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=MAGIC))
        start = src.tell()
        cipher_length = source.stat().st_size - start - 16
        if cipher_length <= 0:
            raise ValueError("Missing ciphertext")
        src.seek(-16, os.SEEK_END)
        tag = src.read(16)
        src.seek(start)
        decryptor = Cipher(algorithms.AES(key), modes.GCM(base64.b64decode(header["nonce"], validate=True), tag)).decryptor()
        decryptor.authenticate_additional_data(MAGIC + length_bytes + header_bytes)
        partial = target.with_suffix(target.suffix + ".unauthenticated")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as out:
                remaining = cipher_length
                while remaining:
                    chunk = src.read(min(CHUNK, remaining))
                    if not chunk:
                        raise ValueError("Truncated ciphertext")
                    remaining -= len(chunk)
                    out.write(decryptor.update(chunk))
                out.write(decryptor.finalize())
            os.replace(partial, target)
        finally:
            partial.unlink(missing_ok=True)
    return {"plaintext_bytes": target.stat().st_size, "recipient": expected}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["keygen", "decrypt", "inspect"])
    parser.add_argument("--private", type=Path)
    parser.add_argument("--public", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--target", type=Path)
    args = parser.parse_args()
    if args.operation == "keygen":
        print(json.dumps({"recipient": generate_keypair(args.private, args.public)}))
    elif args.operation == "decrypt":
        print(json.dumps(open_file(args.source, args.target, args.private)))
    else:
        print(json.dumps(inspect_envelope(args.source)))
