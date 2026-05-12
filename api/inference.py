import json

from api.config import cfg, MODELS_JSON


def query(frame_b64: str, prompt: str) -> str:
    with open(MODELS_JSON) as f:
        defs = json.load(f)
    model = cfg("model")
    endpoint = defs[model]["endpoint"]
    if endpoint == "llamacpp":
        from api.llama_cpp import query as _q
        return _q(frame_b64, prompt)
    else:  # llamacpp_cli
        from api.llama_cpp.llamacpp import query as _q
        return _q(frame_b64, prompt)
