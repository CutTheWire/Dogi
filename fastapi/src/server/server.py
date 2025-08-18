import uvicorn
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

# # 프로젝트 루트를 PYTHONPATH에 추가
# project_root = Path(__file__).parent.parent  # /app/src
# sys.path.insert(0, str(project_root))

from api import v1
from domain import ErrorTools

app = FastAPI()
ErrorTools.ExceptionManager.register(app)

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
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
