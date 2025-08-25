import logging
import re
from pathlib import Path
from typing import Pattern, List
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import yaml

logger = logging.getLogger("bot_filter")

def load_bot_user_agents(file_path: Path) -> Pattern:
    """
    bot.yaml에서 bot_user_agents.name 목록을 읽어 정규식 패턴 컴파일
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        names: List[str] = [x.get("name", "") for x in data.get("bot_user_agents", []) if x.get("name")]
        # 이름 일부가 포함되면 매칭되도록 OR 패턴 구성 (대소문자 무시)
        escaped = [re.escape(n) for n in names if n]
        pattern_str = "|".join(escaped) if escaped else r"$a"  # 비매치 정규식 기본값
        return re.compile(pattern_str, re.IGNORECASE)
    except Exception as e:
        logger.warning(f"Failed to load bot.yaml: {e}")
        return re.compile(r"$a")  # 비매치

class BotBlockerMiddleware(BaseHTTPMiddleware):
    """
    User-Agent가 봇/스캐너 패턴과 매칭되면 403으로 차단
    action=block | log_only (환경변수로 전환 가능)
    """
    def __init__(self, app, pattern: Pattern, action: str = "block"):
        super().__init__(app)
        self.pattern = pattern
        self.action = action.lower()

    async def dispatch(self, request: Request, call_next):
        ua = request.headers.get("user-agent", "")
        if ua and self.pattern.search(ua):
            logger.warning(f"Blocked by bot filter | UA: {ua} | Path: {request.url.path}")
            if self.action == "log_only":
                # 통과시키되 상태에 표시
                request.state.is_bot = True
            else:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Forbidden: automated scanners are not allowed."}
                )
        return await call_next(request)