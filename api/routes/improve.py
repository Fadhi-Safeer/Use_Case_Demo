import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api import state
from api.constants import LLAMA_SERVER_URL, INFERENCE_TIMEOUT
from api.runtime import cfg

router = APIRouter()

_SYSTEM_PROMPT = (
    "You are a prompt engineer specializing in computer vision AI systems. "
    "Rewrite the given prompt into a clear, direct detection instruction for a vision model analyzing live camera frames. "
    "For multiple objects, use the format: 'Detect which of the following are visible in the frame: item1, item2'. "
    "For a single object, use: 'Detect if a [item] is visible in the frame.' "
    "Use natural detection language — never use words like 'labeled', 'annotated', or 'tagged'. "
    "Return only the improved prompt text — no explanation, no preamble, no quotes."
)


@router.post("/improve_prompt")
async def improve_prompt(data: dict):
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return JSONResponse({"error": "No prompt provided"}, status_code=400)

    if state.processing_lock.locked():
        return JSONResponse(
            {"error": "Inference busy — stop live mode first"}, status_code=503
        )

    async with state.processing_lock:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{LLAMA_SERVER_URL}/v1/chat/completions",
                    json={
                        "model": cfg("model"),
                        "max_tokens": 300,
                        "temperature": 0.4,
                        "messages": [
                            {"role": "system", "content": _SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                    },
                    timeout=INFERENCE_TIMEOUT,
                )
                resp.raise_for_status()
                result = resp.json()
                improved = (
                    result.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )
                if not improved:
                    return JSONResponse(
                        {"error": "Model returned empty response"}, status_code=500
                    )
                return JSONResponse({"improved_prompt": improved})
        except httpx.TimeoutException:
            return JSONResponse(
                {"error": "llama-server timeout"}, status_code=504
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
