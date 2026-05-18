from pathlib import Path

# Infrastructure constants
LLAMA_SERVER_URL  = "http://127.0.0.1:8080"
APP_HOST          = "0.0.0.0"
APP_PORT          = 8000
INFERENCE_TIMEOUT = 30
MODELS_JSON       = Path(__file__).parent.parent / "models.json"
