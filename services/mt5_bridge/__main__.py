import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("MT5_BRIDGE_PORT", "5558"))
    uvicorn.run("services.mt5_bridge.main:app", host="0.0.0.0", port=port, log_level="warning")
