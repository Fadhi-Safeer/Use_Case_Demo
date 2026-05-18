"""Inference dispatcher — routes to llama_cpp backend."""
from api.llama_client import query as _llama_query


async def query(frame_b64: str, prompt: str, system_prompt: str = None) -> str:
    """Run inference. system_prompt overrides the backend default when supplied."""
    return await _llama_query(frame_b64, prompt, system_prompt=system_prompt)
