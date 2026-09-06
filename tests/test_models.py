from app.models import DNSResult, HTTPResult, Hop, InvestigationResult


dns = DNSResult(
    resolved=True,
    addresses=["140.82.112.3"],
    responseTimeMs=12.4,
    error=None
)

http = HTTPResult(
    reachable=True,
    status=200,
    responseTimeMs=186.2,
    error=None
)

hop = Hop(
    hop=1,
    ip="192.168.1.1",
    hostname="router",
    rttMs=2.1,
    packetLossPercent=0,
    error=None
)

result = InvestigationResult(
    target="github.com",
    timestamp="2026-09-06T10:30:00Z",
    investigationId="test123",
    dns=dns,
    http=http,
    path=[hop],
    status="completed",
    errors=[]
)

print(result.model_dump_json(indent=2))