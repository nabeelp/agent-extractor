"""Main entry point for agent-extractor application."""

import sys
from .interfaces.mcp_server import start_server


def main():
    """Start the MCP server."""
    print("=" * 60)
    print("Agent Extractor - Document Extraction MCP Server")
    print("=" * 60)
    
    try:
        start_server()
    except KeyboardInterrupt:
        print("\n[Main] Shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"[Main] Failed to start server: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
