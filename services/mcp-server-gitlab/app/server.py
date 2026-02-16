from __future__ import annotations

import ssl

import uvicorn

from .config import get_settings


def main():
    settings = get_settings()

    ssl_cert_reqs = (
        ssl.CERT_REQUIRED if settings.tls_require_client_cert else ssl.CERT_OPTIONAL
    )

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        ssl_certfile=settings.tls_cert_file,
        ssl_keyfile=settings.tls_key_file,
        ssl_ca_certs=settings.tls_ca_file,
        ssl_cert_reqs=ssl_cert_reqs,
    )


if __name__ == "__main__":
    main()

