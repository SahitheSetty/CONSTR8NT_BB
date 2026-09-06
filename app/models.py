from typing import Optional

from pydantic import BaseModel, Field


class DNSResult(BaseModel):
    resolved: bool
    addresses: list[str]
    responseTimeMs: Optional[float] = None
    error: Optional[str] = None


class HTTPResult(BaseModel):
    reachable: bool
    status: Optional[int] = None
    responseTimeMs: Optional[float] = None
    error: Optional[str] = None


class Hop(BaseModel):
    hop: int
    ip: Optional[str] = None
    hostname: Optional[str] = None
    rttMs: Optional[float] = None
    packetLossPercent: Optional[float] = None
    error: Optional[str] = None


class InvestigationResult(BaseModel):
    target: str
    timestamp: str
    investigationId: str

    dns: DNSResult
    http: HTTPResult
    path: list[Hop]

    status: str
    errors: list[str] = Field(default_factory=list)
    