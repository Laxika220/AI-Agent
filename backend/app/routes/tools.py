"""Discovery endpoints: available tools and LLM models."""

from fastapi import APIRouter

from app.core.deps import SettingsDep
from app.models.agent import ModelsInfo, ToolInfo
from app.services.tool_registry import list_tools

router = APIRouter(tags=["tools"])


@router.get("/tools", response_model=list[ToolInfo])
async def get_tools() -> list[ToolInfo]:
    return list_tools()


@router.get("/models", response_model=ModelsInfo)
async def get_models(settings: SettingsDep) -> ModelsInfo:
    available = list(dict.fromkeys([settings.model_name, *settings.available_models]))
    return ModelsInfo(default=settings.model_name, available=available)
