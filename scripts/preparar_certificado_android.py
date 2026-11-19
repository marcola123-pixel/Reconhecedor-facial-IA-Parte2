"""
Prepara o certificado publico TLS para o aplicativo Android.

Execute a partir da raiz do projeto:
    python scripts/preparar_certificado_android.py

Requer certs/cert.pem previamente gerado.
Nao copia a chave privada.
"""

from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "certs" / "cert.pem"
TARGET = (
    ROOT / "android" / "app" / "src" /
    "main" / "res" / "raw" / "server_cert.pem"
)


def main():
    if not SOURCE.is_file():
        raise SystemExit(
            "Certificado nao encontrado em certs/cert.pem. "
            "Gere-o primeiro em uma instalacao nova."
        )

    data = SOURCE.read_bytes()

    if (
        data.count(b"-----BEGIN CERTIFICATE-----") != 1
        or data.count(b"-----END CERTIFICATE-----") != 1
        or b"PRIVATE KEY" in data
    ):
        raise SystemExit("Arquivo de certificado inesperado.")

    if TARGET.exists():
        if TARGET.read_bytes() == data:
            print("Certificado Android ja esta sincronizado.")
            return

        raise SystemExit(
            "Certificado Android diferente. "
            "Nenhum arquivo foi sobrescrito."
        )

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE, TARGET)

    print("Certificado publico copiado para Android.")
    print("Chave privada nao copiada.")


if __name__ == "__main__":
    main()
