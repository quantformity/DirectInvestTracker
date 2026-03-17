"""Pydantic schemas for A2UI backend endpoints."""
from pydantic import BaseModel
from typing import Any


class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    surface_id: str | None = None


class UserActionRequest(BaseModel):
    surface_id: str
    name: str
    context: dict[str, Any] = {}
    conversation: list[ChatMessage] = []


class SurfaceRecord(BaseModel):
    id: str
    title: str
    snapshot: str
    created_at: str

    model_config = {"from_attributes": True}


class SaveSurfaceRequest(BaseModel):
    id: str
    title: str
    snapshot: str
