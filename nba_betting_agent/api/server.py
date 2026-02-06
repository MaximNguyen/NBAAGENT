"""Uvicorn entry point for the dashboard server."""

import os

import uvicorn


def main():
    """Start the NBA Dashboard API server."""
    host = os.getenv("DASHBOARD_HOST", "127.0.0.1")
    port = int(os.getenv("DASHBOARD_PORT", "8000"))
    reload = os.getenv("DASHBOARD_RELOAD", "false").lower() == "true"

    # Load .env if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    uvicorn.run(
        "nba_betting_agent.api.app:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )


if __name__ == "__main__":
    main()
