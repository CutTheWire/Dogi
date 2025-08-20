from fastapi import APIRouter

from . import llm_controller, auth_controller

version_1 = APIRouter()

version_1.include_router(
    llm_controller.llm_router,
    prefix="/LLM",
    tags=["LLM Router"]
)

version_1.include_router(
    auth_controller.auth_router,
    prefix="/Auth",
    tags=["Auth Router"]
)