"""Pydantic v2 response models for the API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# --- Auth ---

class LoginRequest(BaseModel):
    email: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=72)  # bcrypt truncates at 72 bytes


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=72)
    display_name: str | None = Field(default=None, max_length=255)


class GoogleAuthRequest(BaseModel):
    id_token: str = Field(..., min_length=1, max_length=8192)


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=4096)


class MessageResponse(BaseModel):
    message: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1, max_length=4096)


# --- Health ---

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    timestamp: str


# --- Opportunities ---

class OpportunityResponse(BaseModel):
    game_id: str
    matchup: str
    market: str
    outcome: str
    bookmaker: str
    our_prob: float
    market_odds: float
    fair_odds: float
    ev_pct: float
    kelly_bet_pct: float
    confidence: str
    sharp_edge: Optional[float] = None
    rlm_signal: Optional[str] = None
    llm_insight: Optional[str] = None
    ml_prob: Optional[float] = None
    ml_explanation: Optional[str] = None


class OpportunitiesListResponse(BaseModel):
    opportunities: list[OpportunityResponse]
    total: int
    filters_applied: dict = Field(default_factory=dict)


# --- Analysis ---

class AnalysisRunRequest(BaseModel):
    query: str = Field(default="find best bets tonight", min_length=1, max_length=500)
    min_ev: Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    confidence: Optional[str] = Field(default=None, max_length=20)
    limit: Optional[int] = Field(default=None, ge=1, le=100)


class AnalysisRunResponse(BaseModel):
    run_id: str
    status: str
    message: str


class AnalysisStatusResponse(BaseModel):
    run_id: str
    status: str  # "pending", "running", "completed", "error"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    current_step: Optional[str] = None
    opportunities: list[OpportunityResponse] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    recommendation: Optional[str] = None


# --- Odds Comparison ---

class OddsOutcome(BaseModel):
    outcome: str
    bookmaker: str
    price: float
    point: Optional[float] = None


class OddsComparisonResponse(BaseModel):
    game_id: str
    matchup: str
    market: str
    outcomes: list[OddsOutcome]
    best_odds: dict[str, OddsOutcome] = Field(default_factory=dict)


# --- Metrics ---

class SportsbookMetricsResponse(BaseModel):
    name: str
    games_with_odds: int
    markets_available: list[str]
    last_seen: Optional[str] = None
    availability_pct: float


class CacheMetricsResponse(BaseModel):
    hits: int
    misses: int
    stale_hits: int
    hit_rate: float
    fresh_hit_rate: float


# --- History ---

class PerformanceSummary(BaseModel):
    total_bets: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    net_profit: float = 0.0
    roi_pct: float = 0.0
    avg_edge: float = 0.0
    brier_score: Optional[float] = None


class MonthlyROI(BaseModel):
    month: str
    bets: int
    roi_pct: float
    net_profit: float


class ModelAccuracy(BaseModel):
    brier_score: float = 0.0
    calibration_error: float = 0.0
    clv_pct: Optional[float] = None
    total_predictions: int = 0


# --- Admin ---

class UserAdminResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str] = None
    role: str
    email_verified: bool
    has_google: bool
    created_at: str


class UserListResponse(BaseModel):
    users: list[UserAdminResponse]
    total: int
    skip: int
    limit: int


class UpdateUserRoleRequest(BaseModel):
    role: str = Field(..., pattern=r"^(user|admin)$")


class SystemStatsResponse(BaseModel):
    total_users: int
    verified_users: int
    google_users: int
    signups_today: int
    signups_this_week: int


class AuditLogEntry(BaseModel):
    id: int
    timestamp: str
    admin_id: str
    action: str
    target_id: Optional[str] = None
    details: Optional[str] = None


class AuditLogResponse(BaseModel):
    entries: list[AuditLogEntry]
    total: int
