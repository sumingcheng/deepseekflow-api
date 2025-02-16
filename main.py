from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
import json
import asyncio
from config import Config
from schemas import (
    ChatMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
    DeltaMessage,
    ChatCompletionResponseChoice
)
import logging  # 添加在文件开头的导入部分

app = FastAPI()

# 设置日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def process_stream_response(response: httpx.Response):
    """处理上游API的流式响应并转换为OpenAI格式"""
    try:
        is_thinking = True
        # 使用 aiter_bytes 替代 aiter_lines，手动处理数据块
        buffer = b""
        async for chunk in response.aiter_bytes():
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue

                if line == b"data: [DONE]":
                    yield "data: [DONE]\n\n"
                    return

                if not line.startswith(b"data: "):
                    continue

                try:
                    json_data = json.loads(line.replace(b"data: ", b"").decode('utf-8'))
                    
                    delta_content = None
                    if "choices" in json_data and json_data["choices"]:
                        choice = json_data["choices"][0]
                        if "delta" in choice and "content" in choice["delta"]:
                            delta_content = choice["delta"]["content"]

                    if delta_content == "<think>":
                        continue
                            
                    delta = DeltaMessage(content=None, reasoning_content=None)
                    
                    if delta_content == "</think>":
                        is_thinking = False
                        continue
                    
                    if is_thinking:
                        delta.reasoning_content = delta_content
                    else:
                        delta.content = delta_content
                    
                    choice = ChatCompletionResponseChoice(
                        index=0,
                        delta=delta,
                        finish_reason=None
                    )

                    response_data = {
                        "id": json_data.get("id", ""),
                        "object": "chat.completion.chunk",
                        "created": int(json_data.get("created", 0)),
                        "model": "deepseek-reasoner",
                        "system_fingerprint": "fp_7e73fd9a08",
                        "choices": [choice.model_dump(exclude_none=False)]
                    }

                    # 立即发送当前数据块
                    yield f"data: {json.dumps(response_data)}\n\n"

                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {str(e)}, line: {line}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing stream: {str(e)}", exc_info=True)
                    continue

    except Exception as e:
        logger.error(f"Stream processing error: {str(e)}", exc_info=True)
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """处理聊天完成请求"""
    try:
        upstream_data = request.model_dump(exclude_none=True)
        logger.info(f"Received chat completion request: {upstream_data}")

        # 设置更激进的客户端参数
        async with httpx.AsyncClient(
            verify=False,
            timeout=httpx.Timeout(None),  # 禁用超时
            limits=httpx.Limits(max_keepalive_connections=None, max_connections=None)
        ) as client:
            try:
                response = await client.post(
                    Config.UPSTREAM_API_URL,
                    json=upstream_data,
                    headers={
                        "Content-Type": "application/json",
                        "Connection": "keep-alive"
                    }
                )
                
                if request.stream:
                    return StreamingResponse(
                        process_stream_response(response),
                        media_type="text/event-stream",
                        headers={
                            "Cache-Control": "no-cache, no-transform",
                            "Connection": "keep-alive",
                            "X-Accel-Buffering": "no",
                            "Transfer-Encoding": "chunked"
                        }
                    )

                # 处理非流式响应
                if not response.is_success:
                    error_msg = f"Upstream API error: {response.text}"
                    logger.error(error_msg)
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=error_msg
                    )

                response_data = response.json()
                logger.info("Successfully processed non-streaming response")
                return ChatCompletionResponse(**response_data)

            except httpx.TimeoutException as e:
                error_msg = f"Upstream API timeout: {str(e)}"
                logger.error(error_msg)
                if request.stream:
                    async def timeout_stream():
                        yield f"data: {json.dumps({'error': error_msg})}\n\n"
                        yield "data: [DONE]\n\n"
                    return StreamingResponse(
                        timeout_stream(),
                        media_type="text/event-stream"
                    )
                raise HTTPException(status_code=504, detail=error_msg)

    except Exception as e:
        error_msg = f"Internal server error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        if request.stream:
            async def error_stream():
                yield f"data: {json.dumps({'error': error_msg})}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(
                error_stream(),
                media_type="text/event-stream"
            )
        raise HTTPException(status_code=500, detail=error_msg)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=Config.PORT)
