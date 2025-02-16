from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str
    name: Optional[str] = None


class DeltaMessage(BaseModel):
    content: Optional[str] = None
    reasoning_content: Optional[str] = None
    role: Optional[str] = None


class ChatCompletionResponseChoice(BaseModel):
    index: int
    delta: Optional[DeltaMessage] = None
    message: Optional[ChatMessage] = None
    finish_reason: Optional[str] = None


class UsageInfo(BaseModel):
    completion_tokens: Optional[int] = None
    prompt_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    prompt_tokens_details: Optional[Dict[str, Any]] = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[List[str]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = 0
    frequency_penalty: Optional[float] = 0
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionResponseChoice]
    usage: Optional[UsageInfo] = None
    system_fingerprint: Optional[str] = None
