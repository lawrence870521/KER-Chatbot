"""
KER AI Chatbot - FastAPI Backend
架構: Manager → Chat UI → Claude (Tool Use) → KER API → Oracle DB
"""
import json
import os
from typing import AsyncGenerator

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ker_tools import TOOL_DEFINITIONS, execute_tool
from system_prompt import KER_SYSTEM_PROMPT

load_dotenv()

app = FastAPI(title="KER AI Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-opus-4-6"


# ─── Request / Response Models ────────────────────────────────────────────────

class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[Message] = []


# ─── Agentic Loop with Streaming ─────────────────────────────────────────────

async def run_chat_stream(user_message: str, history: list[Message]) -> AsyncGenerator[str, None]:
    """
    執行 Claude agentic loop：
    1. 送給 Claude（含 tools）
    2. 若 Claude 要 call tool → 執行 KER API → 把結果回給 Claude
    3. 最終回應以 streaming 方式輸出
    """
    # 建立對話歷史
    messages = [{"role": m.role, "content": m.content} for m in history]
    messages.append({"role": "user", "content": user_message})

    MAX_ITERATIONS = 5  # 防止無限迴圈

    for iteration in range(MAX_ITERATIONS):
        # 非最後一輪：不用 streaming，等待 tool call 判斷
        if iteration < MAX_ITERATIONS - 1:
            response = await client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=KER_SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=messages,
                thinking={"type": "adaptive"},
            )
        else:
            # 超過 iteration 上限，強制結束
            yield "data: [DONE]\n\n"
            return

        # 如果 Claude 要呼叫 tool
        if response.stop_reason == "tool_use":
            # 把 assistant 的回應加進 history
            messages.append({
                "role": "assistant",
                "content": response.content,
            })

            # 執行所有 tool calls，收集結果
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    # 讓前端知道目前在呼叫哪個 API
                    tool_msg = f"data: {{\"type\": \"tool_call\", \"tool\": \"{block.name}\", \"input\": {json.dumps(block.input, ensure_ascii=False)}}}\n\n"
                    yield tool_msg

                    result = await execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            # 把 tool results 加進 history
            messages.append({
                "role": "user",
                "content": tool_results,
            })
            # 繼續下一輪

        elif response.stop_reason in ("end_turn", "stop_sequence"):
            # Claude 完成回答，改用 streaming 輸出最終結果
            # 重新用 streaming 呼叫，傳入完整對話（含所有 tool 結果）
            async with client.messages.stream(
                model=MODEL,
                max_tokens=4096,
                system=KER_SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    # SSE format
                    payload = json.dumps({"type": "text", "content": text}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"

            yield "data: [DONE]\n\n"
            return
        else:
            # 其他 stop reason（如 max_tokens）
            yield f"data: {{\"type\": \"error\", \"content\": \"Unexpected stop reason: {response.stop_reason}\"}}\n\n"
            yield "data: [DONE]\n\n"
            return

    yield "data: [DONE]\n\n"


# ─── API Endpoints ────────────────────────────────────────────────────────────

@app.post("/chat")
async def chat(request: ChatRequest):
    """Streaming chat endpoint"""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    return StreamingResponse(
        run_chat_stream(request.message, request.history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": MODEL,
        "ker_api": os.getenv("KER_API_BASE_URL", "not configured"),
    }


# 提供前端靜態檔案
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
