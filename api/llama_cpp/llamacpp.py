import re
import requests
from api.config import cfg, INFERENCE_TIMEOUT, LLAMA_SERVER_URL

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_STOP_TOKENS = ["<|im_end|>", "<|endoftext|>", "</s>"]

def query(frame_b64: str, prompt: str) -> str:
    """Send image + prompt to llama-server. Blocking — run via run_in_executor."""
    num_predict = int(cfg("num_predict"))
    image_url = f"data:image/jpeg;base64,{frame_b64}"

    payload = {
        "messages": [
            {
               "role": "system",
                "content": cfg("system_prompt"),
            },
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "max_tokens": num_predict,
        "temperature": 0.1,
        "repeat_penalty": 1.3,
        "stop": ["<|im_end|>", "<|endoftext|>", "</s>", "\n\n"],
        "stream": False,
    }

    try:
        resp = requests.post(
            f"{LLAMA_SERVER_URL}/v1/chat/completions",
            json=payload,
            timeout=INFERENCE_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
    except requests.exceptions.ConnectionError:
        return "[ERROR] llama-server not running. Start it first."
    except requests.exceptions.Timeout:
        return "[TIMEOUT] Inference exceeded 30s"
    except Exception as e:
        return f"[ERROR] {str(e)}"

    for tok in _STOP_TOKENS:
        text = text.replace(tok, "")
    text = _THINK_RE.sub("", text).strip()

    # Hard word limit safety net
    words = text.split()
    if len(words) > 10:
        text = " ".join(words[:10])

    return text
