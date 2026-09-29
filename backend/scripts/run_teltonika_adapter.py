"""Run the standalone Teltonika AVL TCP adapter."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import SessionLocal  # noqa: E402
from services.teltonika_tcp_server import TeltonikaTcpServer, configured_address  # noqa: E402


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    address = configured_address()
    server = TeltonikaTcpServer(address, SessionLocal)
    logging.getLogger("velcore.teltonika").info("Listening on %s:%s", *address)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
