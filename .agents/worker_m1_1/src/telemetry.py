"""
Telemetry and metrics tracking for the Translation Kiosk.
Provides non-blocking latency tracking, rolling percentiles, API call logs, and WebSocket payload serializers.
"""
from dataclasses import dataclass, asdict, field
from collections import deque
from typing import List, Dict, Any, Optional
import time
import math
import asyncio

@dataclass
class ChunkTelemetry:
    """Detailed telemetry record for a single processed audio window/chunk."""
    chunk_id: int
    timestamp: float
    audio_duration_s: float
    buffer_depth_bytes: int
    whisper_latency_ms: float
    qwen_latency_ms: float
    alignment_latency_ms: float
    e2e_latency_ms: float
    source_language: str
    is_english_bypassed: bool
    status: str = "success"
    error: Optional[str] = None
    naive_text: str = ""
    sliding_window_text: str = ""
    corrected_text: str = ""
    translated_text: str = ""
    repairs_count: int = 0

@dataclass
class APICallLog:
    """Structured log entry for Whisper and Qwen HTTP API calls."""
    timestamp: float
    endpoint: str
    method: str
    status_code: int
    latency_ms: float
    payload_summary: str = ""
    response_summary: str = ""
    error: Optional[str] = None

class TelemetryCollector:
    """
    Non-blocking, thread-safe / async-safe telemetry collector.
    Maintains rolling ring buffers for chunk latencies and API call audit logs.
    """
    def __init__(self, history_size: int = 100, log_size: int = 100):
        self.history_size = history_size
        self.log_size = log_size
        self.chunk_history: deque[ChunkTelemetry] = deque(maxlen=history_size)
        self.api_logs: deque[APICallLog] = deque(maxlen=log_size)
        self.start_time: float = time.time()
        
        # Cumulative counters
        self.total_chunks: int = 0
        self.total_audio_seconds: float = 0.0
        self.total_whisper_errors: int = 0
        self.total_qwen_errors: int = 0
        self.total_bypasses: int = 0
        self.total_boundary_corrections: int = 0

    def record_chunk(self, telemetry: ChunkTelemetry) -> None:
        """Records telemetry for a processed chunk and updates rolling counters."""
        self.chunk_history.append(telemetry)
        self.total_chunks += 1
        self.total_audio_seconds += telemetry.audio_duration_s
        
        if telemetry.is_english_bypassed:
            self.total_bypasses += 1
            
        if telemetry.error:
            if telemetry.whisper_latency_ms == 0.0:
                self.total_whisper_errors += 1
            else:
                self.total_qwen_errors += 1
                
        if telemetry.repairs_count > 0:
            self.total_boundary_corrections += telemetry.repairs_count
        elif telemetry.naive_text and telemetry.sliding_window_text:
            if telemetry.naive_text.strip() != telemetry.sliding_window_text.strip():
                self.total_boundary_corrections += 1

    def log_api_call(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        latency_ms: float,
        payload_summary: str = "",
        response_summary: str = "",
        error: Optional[str] = None
    ) -> None:
        """Logs an API interaction for admin panel inspection and debugging."""
        log_entry = APICallLog(
            timestamp=time.time(),
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            latency_ms=round(latency_ms, 2),
            payload_summary=payload_summary[:120] if payload_summary else "",
            response_summary=response_summary[:120] if response_summary else "",
            error=error
        )
        self.api_logs.append(log_entry)

    @staticmethod
    def compute_percentiles(values: List[float]) -> Dict[str, float]:
        """Calculates min, max, avg, p50, p90, and p95 without external dependencies."""
        if not values:
            return {"min": 0.0, "max": 0.0, "avg": 0.0, "p50": 0.0, "p90": 0.0, "p95": 0.0}
        s = sorted(values)
        n = len(s)
        
        def p(pct: float) -> float:
            k = (n - 1) * (pct / 100.0)
            f = math.floor(k)
            c = math.ceil(k)
            if f == c:
                return s[int(k)]
            return s[int(f)] * (c - k) + s[int(c)] * (k - f)

        return {
            "min": round(min(s), 2),
            "max": round(max(s), 2),
            "avg": round(sum(s) / n, 2),
            "p50": round(p(50), 2),
            "p90": round(p(90), 2),
            "p95": round(p(95), 2),
        }

    def get_summary_stats(self) -> Dict[str, Any]:
        """Calculates aggregated metrics over the active rolling window."""
        whisper_latencies = [c.whisper_latency_ms for c in self.chunk_history if c.whisper_latency_ms > 0]
        qwen_latencies = [c.qwen_latency_ms for c in self.chunk_history if not c.is_english_bypassed and c.qwen_latency_ms > 0]
        e2e_latencies = [c.e2e_latency_ms for c in self.chunk_history if c.e2e_latency_ms > 0]

        uptime_sec = time.time() - self.start_time
        bypass_rate = (self.total_bypasses / self.total_chunks * 100.0) if self.total_chunks > 0 else 0.0

        return {
            "uptime_seconds": round(uptime_sec, 1),
            "total_chunks_processed": self.total_chunks,
            "total_audio_seconds": round(self.total_audio_seconds, 2),
            "total_bypasses": self.total_bypasses,
            "bypass_rate_pct": round(bypass_rate, 1),
            "boundary_corrections_count": self.total_boundary_corrections,
            "whisper_latency": self.compute_percentiles(whisper_latencies),
            "qwen_latency": self.compute_percentiles(qwen_latencies),
            "e2e_latency": self.compute_percentiles(e2e_latencies),
            "errors": {
                "whisper_errors": self.total_whisper_errors,
                "qwen_errors": self.total_qwen_errors,
                "total_errors": self.total_whisper_errors + self.total_qwen_errors
            }
        }

    def get_admin_telemetry_payload(self) -> Dict[str, Any]:
        """Formats comprehensive telemetry snapshot for /ws/admin WebSocket broadcast."""
        latest_chunk = self.chunk_history[-1] if self.chunk_history else None
        recent_logs = [asdict(log) for log in list(self.api_logs)[-15:]]

        return {
            "type": "admin_telemetry",
            "stats": self.get_summary_stats(),
            "latest_chunk": asdict(latest_chunk) if latest_chunk else None,
            "recent_logs": recent_logs
        }

    def reset(self) -> None:
        """Resets all rolling buffers and counters."""
        self.chunk_history.clear()
        self.api_logs.clear()
        self.start_time = time.time()
        self.total_chunks = 0
        self.total_audio_seconds = 0.0
        self.total_whisper_errors = 0
        self.total_qwen_errors = 0
        self.total_bypasses = 0
        self.total_boundary_corrections = 0

# Aliases for interface compatibility
TelemetryTracker = TelemetryCollector
TelemetryMetrics = TelemetryCollector
