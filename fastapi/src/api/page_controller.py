from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

page_router = APIRouter()

# HTML 템플릿 디렉토리 설정 - Docker 컨테이너 경로에 맞게 수정
templates = Jinja2Templates(directory="../static/html")

@page_router.get("/", response_class=HTMLResponse, summary="메인 페이지")
async def index(request: Request):
    """
    메인 페이지를 반환합니다.
    """
    return templates.TemplateResponse("index.html", {"request": request})

@page_router.get("/login", response_class=HTMLResponse, summary="로그인 페이지")
async def login_page(request: Request):
    """
    로그인 페이지를 반환합니다.
    """
    return templates.TemplateResponse("login.html", {"request": request})

@page_router.get("/chat", response_class=HTMLResponse, summary="채팅 페이지")
async def chat_page(request: Request):
    """
    채팅 페이지를 반환합니다.
    """
    return templates.TemplateResponse("chat.html", {"request": request})
