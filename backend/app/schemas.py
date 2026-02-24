from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field
from app.models import CategoryEnum


# ─── Account ────────────────────────────────────────────────────────────────

class AccountBase(BaseModel):
    name: str
    base_currency: str = "CAD"


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    base_currency: Optional[str] = None


class AccountOut(AccountBase):
    id: int

    model_config = {"from_attributes": True}


# ─── Position ────────────────────────────────────────────────────────────────

class PositionBase(BaseModel):
    account_id: int
    symbol: str
    category: CategoryEnum
    quantity: float = Field(gt=0)
    cost_per_share: float = Field(ge=0)
    date_added: date = Field(default_factory=date.today)
    yield_rate: Optional[float] = None
    currency: str = "USD"


class PositionCreate(PositionBase):
    pass


class PositionUpdate(BaseModel):
    account_id: Optional[int] = None
    symbol: Optional[str] = None
    category: Optional[CategoryEnum] = None
    quantity: Optional[float] = None
    cost_per_share: Optional[float] = None
    date_added: Optional[date] = None
    yield_rate: Optional[float] = None
    currency: Optional[str] = None


class PositionOut(PositionBase):
    id: int

    model_config = {"from_attributes": True}


# ─── Market Data ─────────────────────────────────────────────────────────────

class MarketDataOut(BaseModel):
    symbol: str
    last_price: Optional[float]
    pe_ratio: Optional[float]
    change_percent: Optional[float]
    beta: Optional[float]
    timestamp: datetime

    model_config = {"from_attributes": True}


# ─── FX Rate ─────────────────────────────────────────────────────────────────

class FxRateOut(BaseModel):
    pair: str
    rate: float
    timestamp: datetime

    model_config = {"from_attributes": True}


# ─── Summary / Enriched Position ─────────────────────────────────────────────

class EnrichedPosition(BaseModel):
    id: int
    symbol: str
    category: CategoryEnum
    account_id: int
    account_name: str
    account_currency: str
    quantity: float
    cost_per_share: float
    date_added: date
    yield_rate: Optional[float]

    stock_currency: str           # position's trading currency
    spot_price: Optional[float]   # in stock_currency
    fx_stock_to_account: float    # stock_currency → account_currency
    fx_account_to_reporting: float  # account_currency → reporting_currency
    mtm_account: float            # spot * qty converted to account currency
    pnl_account: float            # (spot - cost) * qty converted to account currency
    mtm_reporting: float          # mtm_account converted to reporting currency
    pnl_reporting: float          # pnl_account converted to reporting currency
    proportion: float             # % of total portfolio MTM (reporting)


class SummaryGroup(BaseModel):
    group_key: str
    total_mtm_reporting: float
    total_pnl_reporting: float
    proportion: float


class SummaryOut(BaseModel):
    positions: list[EnrichedPosition]
    groups: list[SummaryGroup]
    total_mtm_reporting: float
    total_pnl_reporting: float
    reporting_currency: str


# ─── History ─────────────────────────────────────────────────────────────────

class HistoryPoint(BaseModel):
    date: date
    close_price: float
    pnl: float
    mtm: float
    cash_gic: float = 0.0   # MTM of Cash + GIC positions only (0 for symbol view)


class HistoryOut(BaseModel):
    symbol: str
    account_id: Optional[int]
    points: list[HistoryPoint]


# ─── AI ──────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    reply: str
    pending_sql: str | None = None   # set when the bot wants the user to confirm a query


class SqlExecuteRequest(BaseModel):
    sql: str
    question: str


class ChartRequest(BaseModel):
    prompt: str


class ChartResponse(BaseModel):
    type: str   # "image" | "plotly" | "table" | "error"
    data: str   # base64 PNG, JSON string, or error message


class ActionPlan(BaseModel):
    action: str        # "add_position" | "delete_position" | "record_cash" | "record_dividend" | "none"
    description: str = ""
    params: dict = {}


class ActionRequest(BaseModel):
    message: str


class ExecuteActionRequest(BaseModel):
    action: str
    params: dict


class ExecuteActionResponse(BaseModel):
    success: bool
    message: str


# ─── AI Settings ──────────────────────────────────────────────────────────────

class OllamaSettingsOut(BaseModel):
    # Active provider
    ai_provider: str = "ollama"
    # Ollama
    ollama_base_url: str
    ollama_model: str
    ollama_code_model: str
    # LM Studio
    lmstudio_base_url: str = "http://localhost:1234/v1"
    lmstudio_model: str = ""
    lmstudio_code_model: str = ""
    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_code_model: str = "gemini-2.0-flash"
    # Claude
    claude_api_key: str = ""
    claude_model: str = "claude-3-5-haiku-20241022"
    claude_code_model: str = "claude-3-5-haiku-20241022"
    # llama.cpp server
    llamacpp_base_url: str = "http://localhost:8080/v1"
    llamacpp_model: str = ""
    llamacpp_code_model: str = ""
    # History cache
    history_cache_path: str = ""


class OllamaSettingsUpdate(BaseModel):
    # Active provider
    ai_provider: str = "ollama"
    # Ollama
    ollama_base_url: str
    ollama_model: str
    ollama_code_model: str
    # LM Studio
    lmstudio_base_url: str = "http://localhost:1234/v1"
    lmstudio_model: str = ""
    lmstudio_code_model: str = ""
    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_code_model: str = "gemini-2.0-flash"
    # Claude
    claude_api_key: str = ""
    claude_model: str = "claude-3-5-haiku-20241022"
    claude_code_model: str = "claude-3-5-haiku-20241022"
    # llama.cpp server
    llamacpp_base_url: str = "http://localhost:8080/v1"
    llamacpp_model: str = ""
    llamacpp_code_model: str = ""
    # History cache
    history_cache_path: str = ""
