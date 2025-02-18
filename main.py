from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
import httpx
import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional
from config import Config
from schemas import ChatCompletionRequest

app = FastAPI()

# 设置日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def format_sse_response(response: Dict[str, Any], content_type: str) -> bytes:
    """
    将模型 API 响应格式化为 SSE 格式

    Args:
        response: 原始 API 响应数据
        content_type: 内容类型 ('THINK' 或 'TEXT')

    Returns:
        bytes: 格式化后的 SSE 消息
    """
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


async def process_model_chunk(chunk: bytes, content_type: Optional[str]) -> AsyncGenerator[bytes, None]:
    """
    处理模型返回的数据块

    Args:
        chunk: 原始数据块
        content_type: 当前内容类型

    Yields:
        bytes: 处理后的 SSE 消息
    """
    chunk_text = chunk.decode("utf-8")
    logger.debug(f"Received chunk: {chunk_text}")

    for line in chunk_text.strip().split('\n'):
        if not line.startswith("data: "):
            continue

        if line == "data: [DONE]":
            continue

        try:
            data = json.loads(line[6:])
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}, line: {line}")
            continue

        choices = data.get("choices", [])
        if not choices:
            yield f"data: {json.dumps(data)}\n\n".encode('utf-8')
            continue

        delta_content = choices[0].get("delta", {}).get("content", "")
        if delta_content == "<think>":
            content_type = "THINK"
            continue
        elif delta_content == "</think>":
            content_type = "TEXT"
            continue

        if content_type:
            yield await format_sse_response(data, content_type)


async def create_model_request(request_body: ChatCompletionRequest) -> Dict[str, Any]:
    """
    创建发送给模型的请求数据

    Args:
        request_body: 客户端请求体

    Returns:
        Dict[str, Any]: 格式化后的请求数据
    """
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

    return request_data


@app.post("/v1/chat/completions")
async def create_chat_completion(request_body: ChatCompletionRequest, request: Request):
    """
    处理聊天补全请求的端点

    Args:
        request_body: 请求体
        request: FastAPI 请求对象

    Returns:
        StreamingResponse: SSE 流式响应

    Raises:
        HTTPException: 当请求无效或处理出错时
    """
    try:
        raw_request = await request.json()
        logger.info(f"Incoming request: {raw_request}")

        if not request_body.messages:
            raise HTTPException(status_code=400, detail="Empty message list")

        async def stream_response():
            content_type: Optional[str] = None

            async with httpx.AsyncClient() as client:
                try:
                    request_data = await create_model_request(request_body)

                    async with client.stream(
                            "POST",
                            Config.UPSTREAM_API_URL,
                            json=request_data,
                            timeout=None
                    ) as model_response:
                        async for chunk in model_response.aiter_bytes():
                            async for processed_chunk in process_model_chunk(chunk, content_type):
                                yield processed_chunk

                except httpx.HTTPStatusError as e:
                    error_msg = f'data: {{"error": "Model API Error: {e.status_code}"}}\n\n'
                    yield error_msg.encode()
                except Exception as e:
                    error_msg = f'data: {{"error": "Processing Error: {str(e)}"}}\n\n'
                    yield error_msg.encode()

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
