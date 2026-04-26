"""TLS/HTTPS 支持"""

import os
import subprocess
from pathlib import Path
from datetime import datetime, timedelta


CERT_DIR = Path("/etc/ubunturouter/tls")
CERT_PATH = CERT_DIR / "cert.pem"
KEY_PATH = CERT_DIR / "key.pem"


def cert_exists() -> bool:
    """证书是否已存在"""
    return CERT_PATH.exists() and KEY_PATH.exists()


def ensure_cert():
    """确保证书存在（不存在则自签）"""
    if cert_exists():
        return
    CERT_DIR.mkdir(parents=True, exist_ok=True)

    # 使用 openssl 生成自签证书
    try:
        subprocess.run(
            [
                "openssl", "req", "-x509", "-newkey", "rsa:2048",
                "-keyout", str(KEY_PATH),
                "-out", str(CERT_PATH),
                "-days", "3650",
                "-nodes",
                "-subj", "/CN=ubunturouter.local/O=UbuntuRouter",
            ],
            capture_output=True, timeout=30, check=True
        )
        KEY_PATH.chmod(0o600)
        CERT_PATH.chmod(0o644)
    except Exception as e:
        # fallback: 使用 Python 生成
        _generate_self_signed_cert_python()


def _generate_self_signed_cert_python():
    """Python 内置方法生成自签证书"""
    try:
        import ssl
        cert_pem, key_pem = _make_self_signed_cert()
        CERT_PATH.write_text(cert_pem)
        KEY_PATH.write_text(key_pem)
        KEY_PATH.chmod(0o600)
    except ImportError:
        raise RuntimeError("无法生成自签证书，请安装 openssl")


def _make_self_signed_cert():
    """生成自签证书（纯 Python）"""
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    import ipaddress

    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "UbuntuRouter"),
        x509.NameAttribute(NameOID.COMMON_NAME, "ubunturouter.local"),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("ubunturouter.local"),
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            ]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()

    return cert_pem, key_pem


def init_https():
    """初始化 HTTPS"""
    ensure_cert()
    return str(CERT_PATH), str(KEY_PATH)
