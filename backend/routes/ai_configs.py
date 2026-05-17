from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models.schemas import AiConfigCreate, AiConfigUpdate
from services.ai_config_service import (
    create_ai_config,
    delete_ai_config,
    get_ai_config,
    get_default_ai_config,
    list_ai_configs,
    list_ai_models,
    test_ai_config,
    update_ai_config,
)


router = APIRouter(prefix="/api/ai-configs", tags=["ai-configs"])


@router.get("")
def get_ai_configs():
    return list_ai_configs()


@router.get("/default")
def get_default_config():
    config = get_default_ai_config()
    if not config:
        raise HTTPException(status_code=404, detail="还没有可用的 AI 配置")
    return config


@router.get("/{config_id}")
def get_config(config_id: int):
    config = get_ai_config(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="AI 配置不存在")
    return config


@router.post("")
def post_ai_config(payload: AiConfigCreate):
    try:
        return create_ai_config(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{config_id}")
def patch_ai_config(config_id: int, payload: AiConfigUpdate):
    try:
        config = update_ai_config(config_id, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not config:
        raise HTTPException(status_code=404, detail="AI 配置不存在")
    return config


@router.delete("/{config_id}")
def remove_ai_config(config_id: int):
    deleted = delete_ai_config(config_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="AI 配置不存在")
    return {"deleted": True, "id": config_id}


@router.post("/{config_id}/test")
async def test_config(config_id: int):
    result = await test_ai_config(config_id)
    if not result:
        raise HTTPException(status_code=404, detail="AI 配置不存在")
    return result


@router.get("/{config_id}/models")
async def get_config_models(config_id: int):
    result = await list_ai_models(config_id)
    if not result:
        raise HTTPException(status_code=404, detail="AI 配置不存在")
    return result
