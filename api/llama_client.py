import re
import httpx
from api.constants import INFERENCE_TIMEOUT, LLAMA_SERVER_URL
from api.runtime import cfg

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_STOP_TOKENS = ["<|im_end|>", "<|endoftext|>", "</s>"]


async def query(frame_b64: str, prompt: str, system_prompt: str = None) -> str:
    """Send image + prompt to llama-server. Native coroutine.

    system_prompt: if provided, overrides the stored system prompt.
    """
    num_predict = int(cfg("num_predict"))
    image_url = f"data:image/jpeg;base64,{frame_b64}"

    # Use caller-supplied system_prompt, or fall back to legacy key if set
    sys_content = system_prompt if system_prompt is not None else ""

    payload = {
        "messages": [
            {
                "role": "system",
                "content": sys_content,
            },
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": prompt},
                ],
            },
        ],
        "max_tokens": num_predict,
        "temperature": 0.1,
        "repeat_penalty": 1.3,
        "stop": ["<|im_end|>", "<|endoftext|>", "</s>", "\n\n"],
        "stream": False,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{LLAMA_SERVER_URL}/v1/chat/completions",
                json=payload,
                timeout=INFERENCE_TIMEOUT,
            )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
    except httpx.ConnectError:
        return "[ERROR] llama-server not running. Start it first."
    except httpx.TimeoutException:
        return "[TIMEOUT] Inference exceeded 30s"
    except Exception as e:
        return f"[ERROR] {str(e)}"

    for tok in _STOP_TOKENS:
        text = text.replace(tok, "")
    text = _THINK_RE.sub("", text).strip()

    return text
