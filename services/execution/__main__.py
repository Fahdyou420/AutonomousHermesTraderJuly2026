import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("EXECUTION_PORT", "5563"))
    uvicorn.run("services.execution.main:app", host="0.0.0.0", port=port, log_level="warning")
