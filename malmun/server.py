"""말문 English — local server.

Serves the single-page app and relays its AI requests to the Claude API, so the
API key stays on this machine instead of in the browser.

    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=sk-ant-...
    python server.py                 # then open http://127.0.0.1:8000 in Chrome

The relay forwards whatever prompt the page sends, so keep it bound to localhost.
"""

import json
import os
from pathlib import Path
from typing import Literal

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

MODEL = os.environ.get("MALMUN_MODEL", "claude-opus-5-5")
APP_HTML = Path(__file__).parent / "static" / "app.html"

# app.html follows the claude.ai Artifact page contract (no <html>/<head>/<body>),
# so the same file can be published as-is; wrap it in a document when serving it.
PAGE_HEAD = (
    '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
    "</head><body>"
)
PAGE_TAIL = "</body></html>"

# Tutor turns and grading are conversational and latency-sensitive; the
# end-of-session report gets a little more thinking.
EFFORT = {"quick": "low", "default": "medium"}

app = FastAPI(title="말문 English")
client = anthropic.AsyncAnthropic()


def has_credentials() -> bool:
    # An API key, auth token, or `ant auth login` profile; without one the SDK
    # fails before sending anything.
    return any(getattr(client, name, None) for name in ("api_key", "auth_token", "credentials"))


class ClaudeRequest(BaseModel):
    system: str = Field(max_length=20_000)
    prompt: str = Field(min_length=1, max_length=60_000)
    output_schema: dict = Field(alias="schema")
    tier: Literal["quick", "default"] = "quick"


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return PAGE_HEAD + APP_HTML.read_text(encoding="utf-8") + PAGE_TAIL


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "ai": has_credentials(), "model": MODEL}


@app.post("/api/claude")
async def ask_claude(req: ClaudeRequest) -> dict:
    if not has_credentials():
        raise HTTPException(401, "Claude API 키가 없어요. ANTHROPIC_API_KEY를 설정하고 서버를 다시 실행해 주세요.")
    try:
        response = await client.beta.messages.create(
            model=MODEL,
            max_tokens=8000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=req.system,
            messages=[{"role": "user", "content": req.prompt}],
            output_config={
                "effort": EFFORT[req.tier],
                "format": {"type": "json_schema", "schema": req.output_schema},
            },
        )
    except anthropic.AuthenticationError:
        raise HTTPException(401, "Claude API 키가 올바르지 않아요. ANTHROPIC_API_KEY를 확인해 주세요.")
    except anthropic.PermissionDeniedError:
        raise HTTPException(403, "이 API 키로는 Claude 모델을 쓸 수 없어요.")
    except anthropic.RateLimitError:
        raise HTTPException(429, "요청이 많아요. 잠시 후 다시 시도해 주세요.")
    except anthropic.BadRequestError as e:
        raise HTTPException(400, f"요청 형식 오류: {e.message}")
    except anthropic.APIStatusError as e:
        raise HTTPException(502, f"Claude API 오류 ({e.status_code}). 잠시 후 다시 시도해 주세요.")
    except anthropic.APIConnectionError:
        raise HTTPException(502, "Claude API에 연결하지 못했어요. 네트워크를 확인해 주세요.")

    if response.stop_reason == "refusal":
        raise HTTPException(422, "이 내용에는 답할 수 없어요. 다르게 말해 보세요.")
    if response.stop_reason == "max_tokens":
        raise HTTPException(502, "답변이 너무 길어 중간에 끊겼어요. 다시 시도해 주세요.")
    text = next((block.text for block in response.content if block.type == "text"), None)
    if text is None:
        raise HTTPException(502, "답변을 받지 못했어요. 다시 시도해 주세요.")
    return json.loads(text)


if __name__ == "__main__":
    import uvicorn

    if not has_credentials():
        print("ANTHROPIC_API_KEY가 없어 AI 코치 없이 실행합니다. 레슨과 복습은 그대로 쓸 수 있어요.")
    uvicorn.run(
        app,
        host=os.environ.get("MALMUN_HOST", "127.0.0.1"),
        port=int(os.environ.get("MALMUN_PORT", "8000")),
    )
