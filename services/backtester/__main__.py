import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("BACKTESTER_PORT", "5560"))
    uvicorn.run("services.backtester.main:app", host="0.0.0.0", port=port, log_level="warning")
