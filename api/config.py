from pathlib import Path

# Infrastructure constants
LLAMA_SERVER_URL  = "http://127.0.0.1:8080"
APP_HOST          = "0.0.0.0"
APP_PORT          = 8000
INFERENCE_TIMEOUT = 30
MODELS_JSON       = Path(__file__).parent.parent / "models.json"

_GEAR_SYSTEM = (
    "/no_think You are a construction site safety compliance inspector. "
    "Examine the image. If no worker is visible, answer No. "
    "If a worker is visible, check for a safety helmet or hard hat AND "
    "high-visibility vest. Answer Yes only if both are clearly worn. "
    "Answer No if either is missing, worn incorrectly, or if you are unsure. "
)

_GEAR_USER = "Is the worker wearing all required safety gear? Answer Yes or No only."

_WEAPON_SYSTEM = (
    "/no_think You are a security surveillance AI monitoring a construction site. "
    "Examine the image carefully for any weapons or dangerous objects: "
    "knives, firearms, batons, blades, or similar threats. "
    "Answer with exactly one word: Yes if a weapon or dangerous object is visible, "
    "No if the scene appears safe or if you are unsure."
)

_WEAPON_USER = "Is there a weapon or dangerous object visible in this image? Answer Yes or No only."

_CUSTOM_SYSTEM = (
    "/no_think You are a visual analysis assistant. "
    "Examine the image carefully"
    "Respond with only the detected item or object names if clearly present, or NONE if not detected or unsure."
    "List detected items separated by commas, no explanation, no sentences."
)

_settings = {
    "model":                    "qwen3-vl:2b-cli",
    "num_predict":              512,
    "max_image_size":           640,
    "frame_interval":           2.0,
    "job_timeout_seconds":      120,
    "frame_timeout_seconds":    30,
    "max_queue_size":           50,
    "show_duplicate_results":   False,   # if True, a card is added every cycle even if result text unchanged
    # Per-use-case prompts
    "gear_system_prompt":       _GEAR_SYSTEM,
    "gear_user_prompt":         _GEAR_USER,
    "weapon_system_prompt":     _WEAPON_SYSTEM,
    "weapon_user_prompt":       _WEAPON_USER,
    "custom_system_prompt":     _CUSTOM_SYSTEM,
}


def cfg(key):
    return _settings[key]


def update_cfg(key, value):
    _settings[key] = value
