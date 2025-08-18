from fastapi import APIRouter, Request, Depends, Path
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from domain import ModelRegistry, ErrorTools

mongodb_router = APIRouter()