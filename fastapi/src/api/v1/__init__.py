from fastapi import APIRouter

from . import llm_controller, mongodb_controller

version_1 = APIRouter()

version_1.include_router(
    llm_controller.llm_router,
    prefix="/LLM",
    tags=["LLM Router"]
)

version_1.include_router(
    mongodb_controller.mongodb_router,
    prefix="/mongodb",
    tags=["MongoDB Router"]
)   