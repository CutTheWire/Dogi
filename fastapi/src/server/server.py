import uvicorn
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from api import Page, v1
from core import AppState, bot_filter
from domain import ErrorTools

@asynccontextmanager
async def lifespan(app: FastAPI):
    '''
    FastAPI 애플리케이션의 수명 주기를 관리하는 함수.
    '''
    await AppState.initialize_handlers()
    try:
        yield
    finally:
        await AppState.cleanup_handlers()

app = FastAPI(lifespan=lifespan)

# bot.yaml 로드 및 미들웨어 등록
bot_yaml_path = Path(__file__).resolve().parents[1] / "bot.yaml"
pattern = bot_filter.load_bot_user_agents(bot_yaml_path)
action = os.getenv("BOT_FILTER_ACTION", "block")
app.add_middleware(bot_filter.BotBlockerMiddleware, pattern=pattern, action=action)

# Static 파일 마운트 - Docker 컨테이너 경로에 맞게 수정
app.mount("/static", StaticFiles(directory="../static"), name="static")

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Dogi FastAPI",
        version="v1.0.*",
        summary="반려견 진단 에이전트 API",
        routes=app.routes,
        description=(
            "이 API는 다음과 같은 기능을 제공합니다:\n\n"
            "각 엔드포인트의 자세한 정보는 해당 엔드포인트의 문서에서 확인할 수 있습니다."
        ),
        
    )
    openapi_schema["info"]["x-logo"] = {
        "url": "https://drive.google.com/thumbnail?id=12PqUS6bj4eAO_fLDaWQmoq94-771xfim"
    }
    openapi_schema["components"]["securitySchemes"] = {
    "BearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "JWT 토큰을 입력하세요. 'Bearer ' 접두사는 자동으로 추가됩니다."
    }
}
    app.openapi_schema = openapi_schema
    return app.openapi_schema

ErrorTools.ExceptionManager.register(app)
app.openapi = custom_openapi
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    Page.page_router,
    prefix="",
    tags=["Page Router"]
)

app.include_router(
    v1.version_1,
    prefix="/v1",
    tags=["Version 1 Router"],
    responses={500: {"description": "Internal Server Error"}},
)

if __name__  ==  "__main__":
    uvicorn.run(
        app,
        host = "0.0.0.0",
        port = 80,
        http = "h11",
        loop="asyncio"
    )
