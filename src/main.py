"""Main entry point for agent-extractor application."""

import logging
import sys

from .interfaces.mcp_server import start_server


log = logging.getLogger(__name__)


def main() -> None:
    """Start the MCP server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    log.info("Starting Agent Extractor - Document Extraction MCP Server")

    try:
        start_server()
    except KeyboardInterrupt:
        log.info("Shutting down gracefully after keyboard interrupt")
        sys.exit(0)
    except Exception:  # pragma: no cover - fail fast with context
        log.exception("Failed to start server")
        sys.exit(1)


if __name__ == "__main__":
    main()
