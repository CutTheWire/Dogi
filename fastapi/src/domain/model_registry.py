from __future__ import annotations
from typing import Dict, List, Optional
from pydantic import BaseModel, ValidationError
from pathlib import Path
from functools import lru_cache
import json

class ModelRegistryLoadError(RuntimeError):
    pass

class ModelInfo(BaseModel):
    id: str
    name: str
    vendor: str
    model: str  # 이 필드가 누락되어 있었습니다
    description: str

_JSON_PATH = Path(__file__).parent / "models" / "models.json"

def _load_json() -> Dict[str, ModelInfo]:
    """
    JSON 파일에서 모델 정보를 로드합니다.
    
    Returns:
        Dict[str, ModelInfo]: 모델 ID를 키로 하는 모델 정보 딕셔너리
    """
    if not _JSON_PATH.exists():
        raise ModelRegistryLoadError(f"models.json not found: {_JSON_PATH}")
    try:
        with _JSON_PATH.open("r", encoding="utf-8") as f:
            raw = json.load(f) or {}
    except json.JSONDecodeError as e:
        raise ModelRegistryLoadError(f"Invalid JSON format in {_JSON_PATH}: {e}") from e

    items = raw.get("models", [])
    if not isinstance(items, list):
        raise ModelRegistryLoadError("`models` key must be a list")

    catalog: Dict[str, ModelInfo] = {}
    for item in items:
        try:
            mi = ModelInfo(**item)
            catalog[mi.id] = mi
        except ValidationError as e:
            raise ModelRegistryLoadError(f"Invalid model entry: {item}\n{e}") from e
    return catalog

@lru_cache
def _catalog() -> Dict[str, ModelInfo]:
    """
    캐시된 모델 정보를 반환합니다. 캐시가 비어있으면 JSON 파일에서 로드합니다.
    
    Returns:
        Dict[str, ModelInfo]: 모델 ID를 키로 하는 모델 정보 딕셔너리
    """
    return _load_json()

def list_models(enabled_ids: Optional[List[str]] = None) -> List[ModelInfo]:
    """
    사용 가능한 모델 목록을 반환합니다.
    
    Args:
        enabled_ids (Optional[List[str]]): 특정 모델 ID 목록, None이면 모든 모델 반환
    
    Returns:
        List[ModelInfo]: 모델 정보 리스트
    """
    catalog = _catalog()
    if enabled_ids:
        return [m for mid, m in catalog.items() if mid in enabled_ids]
    return list(catalog.values())

def get_model(model_id: str) -> Optional[ModelInfo]:
    """
    특정 모델 ID에 대한 정보를 반환합니다.
    
    Args:
        model_id (str): 모델 ID
    
    Returns:
        Optional[ModelInfo]: 모델 정보, 존재하지 않으면 None
    """
    return _catalog().get(model_id)

def reload_models() -> None:
    """
    재로드 모델 정보를 캐시에서 제거합니다.
    """
    _catalog.cache_clear()
    _catalog()

if __name__ == "__main__":
    try:
        models = list_models()
        catalog_dict = {m.id: m.model_dump() for m in models}
        print(catalog_dict)
    except ModelRegistryLoadError as e:
        print(f"Error loading models: {e}")