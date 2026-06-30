import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("MCP_BRIDGE_PORT", "5562"))
    uvicorn.run("services.mcp_bridge.main:app", host="0.0.0.0", port=port, log_level="info")
