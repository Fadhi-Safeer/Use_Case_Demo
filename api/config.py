from pathlib import Path

# Infrastructure constants
LLAMA_SERVER_URL  = "http://127.0.0.1:8080"
APP_HOST          = "0.0.0.0"
APP_PORT          = 8000
INFERENCE_TIMEOUT = 30
MODELS_JSON       = Path(__file__).parent.parent / "models.json"

_settings = {
    "model":          "qwen3-vl:2b-cli",
    "num_predict":    64,
    "max_image_size": 640,
    "system_prompt":  "/no_think You are a hand object detector. Look ONLY at what the person's fingers are wrapped around. Name it in 1-3 words. If hands are empty or not visible, say: none.",
}


def cfg(key):
    return _settings[key]


def update_cfg(key, value):
    _settings[key] = value
