from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
import httpx
import json
import logging
from config import Config
from schemas import ChatCompletionRequest

app = FastAPI()

# 设置日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def format_sse(response: dict, content_type: str) -> bytes:
    """Format model API response to SSE format"""
    payload = {
        "id": response.get("id"),
        "object": response.get("object"),
        "created": response.get("created"),
        "model": response.get("model"),
        "system_fingerprint": response.get("system_fingerprint"),
        "choices": [
            {
                "index": choice.get("index"),
                "delta": {
                    "role": choice.get("delta", {}).get("role"),
                    "content": (
                        choice.get("delta", {}).get("content")
                        if content_type != "THINK"
                        else None
                    ),
                    "reasoning_content": (
                        choice.get("delta", {}).get("content")
                        if content_type == "THINK"
                        else None
                    ),
                },
                "logprobs": choice.get("logprobs"),
                "finish_reason": choice.get("finish_reason")
            }
            for choice in response.get("choices", [])
        ]
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


@app.post("/v1/chat/completions")
async def create_chat_completion(request_body: ChatCompletionRequest, request: Request):
    try:
        raw_request = await request.json()
        logger.info(f"Incoming request: {raw_request}")

        if not request_body.messages:
            raise HTTPException(status_code=400, detail="Empty message list")

        async def stream_response():
            content_type = None

            async with httpx.AsyncClient() as client:
                try:
                    request_data = {
                        "model": request_body.model,
                        "messages": [
                            {"role": msg.role, "content": msg.content}
                            for msg in request_body.messages
                        ],
                        "stream": request_body.stream
                    }

                    if request_body.temperature is not None:
                        request_data["temperature"] = request_body.temperature

                    async with client.stream(
                            "POST",
                            Config.UPSTREAM_API_URL,
                            json=request_data,
                            timeout=None
                    ) as model_response:
                        async for chunk in model_response.aiter_bytes():
                            chunk_text = chunk.decode("utf-8")
                            logger.debug(f"Received chunk: {chunk_text}")

                            for line in chunk_text.strip().split('\n'):
                                if not line.startswith("data: "):
                                    continue

                                # 处理流结束标记
                                if line == "data: [DONE]":
                                    continue

                                try:
                                    data = json.loads(line[6:])
                                except json.JSONDecodeError as e:
                                    logger.error(
                                        f"JSON decode error: {e}, line: {line}")
                                    continue

                                choices = data.get("choices", [])
                                if not choices:
                                    yield f"data: {json.dumps(data)}\n\n".encode('utf-8')
                                    continue

                                delta_content = choices[0].get(
                                    "delta", {}).get("content", "")
                                if delta_content == "<think>":
                                    content_type = "THINK"
                                    continue
                                elif delta_content == "</think>":
                                    content_type = "TEXT"
                                    continue

                                if content_type:
                                    yield await format_sse(data, content_type)

                except httpx.HTTPStatusError as e:
                    yield f'data: {{"error": "Model API Error: {e.status_code}"}}\n\n'.encode()
                except Exception as e:
                    yield f'data: {{"error": "Processing Error: {str(e)}"}}\n\n'.encode()

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream"
        )

    except Exception as e:
        logger.error(f"Server error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=Config.PORT)
