import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PAPER_TRADER_PORT", "5561"))
    uvicorn.run("services.paper_trader.main:app", host="0.0.0.0", port=port, log_level="warning")
