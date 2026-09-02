"""3言語共通仕様のスコアリングAPI（Python実装・HTTP層）。

計算ロジックは core.py に置いてある。
Go/Ruby 実装が手動でJSONを解釈しているため、公平性の観点からここでも
pydantic の自動バリデーションは使わず、生のリクエストボディを自前で解釈する。
"""

import json
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core import ValidationError, compute

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

_processed = 0


@app.post("/api/v1/score")
async def score(request: Request):
    global _processed
    try:
        req = json.loads(await request.body())
    except ValueError:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    try:
        body = compute(req)
    except (ValidationError, KeyError, TypeError):
        return JSONResponse({"error": "validation_failed"}, status_code=400)

    _processed += 1
    return body


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "lang": "python"}


@app.get("/metrics")
async def metrics():
    return {"lang": "python", "processed": _processed, "pid": os.getpid()}
