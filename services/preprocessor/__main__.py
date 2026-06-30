import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PREPROCESSOR_PORT", "5559"))
    uvicorn.run("services.preprocessor.main:app", host="0.0.0.0", port=port, log_level="warning")
