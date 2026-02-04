"""
Мониторинг и метрики бота.

Модуль обеспечивает:
- Сбор метрик работы бота
- Health check endpoints
- Статистику производительности
- Алерты о проблемах
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

from bot.config import settings


logger = structlog.get_logger()


# ============================================================
# МЕТРИКИ
# ============================================================

@dataclass
class BotMetrics:
    """Класс для сбора метрик бота."""
    
    # Время старта
    start_time: float = field(default_factory=time.time)
    
    # Счётчики запросов
    messages_received: int = 0
    callbacks_received: int = 0
    commands_executed: int = 0
    
    # Генерации
    generations_started: int = 0
    generations_completed: int = 0
    generations_failed: int = 0
    
    # Платежи
    payments_initiated: int = 0
    payments_completed: int = 0
    payments_failed: int = 0
    total_revenue_kopecks: int = 0
    
    # Ошибки
    errors_total: int = 0
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    
    # Производительность
    avg_response_time_ms: float = 0.0
    _response_times: List[float] = field(default_factory=list)
    
    @property
    def uptime_seconds(self) -> float:
        """Время работы бота в секундах."""
        return time.time() - self.start_time
    
    @property
    def uptime_formatted(self) -> str:
        """Форматированное время работы."""
        seconds = int(self.uptime_seconds)
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}д")
        if hours > 0:
            parts.append(f"{hours}ч")
        if minutes > 0:
            parts.append(f"{minutes}м")
        
        return " ".join(parts) or "< 1м"
    
    def record_message(self):
        """Записать входящее сообщение."""
        self.messages_received += 1
    
    def record_callback(self):
        """Записать callback."""
        self.callbacks_received += 1
    
    def record_command(self):
        """Записать выполненную команду."""
        self.commands_executed += 1
    
    def record_generation_start(self):
        """Записать старт генерации."""
        self.generations_started += 1
    
    def record_generation_complete(self):
        """Записать завершённую генерацию."""
        self.generations_completed += 1
    
    def record_generation_fail(self):
        """Записать неудачную генерацию."""
        self.generations_failed += 1
    
    def record_payment(self, amount_kopecks: int, success: bool):
        """Записать платёж."""
        if success:
            self.payments_completed += 1
            self.total_revenue_kopecks += amount_kopecks
        else:
            self.payments_failed += 1
    
    def record_error(self, error_type: str):
        """Записать ошибку."""
        self.errors_total += 1
        self.errors_by_type[error_type] = self.errors_by_type.get(error_type, 0) + 1
    
    def record_response_time(self, duration_ms: float):
        """Записать время ответа."""
        self._response_times.append(duration_ms)
        
        # Храним только последние 1000 измерений
        if len(self._response_times) > 1000:
            self._response_times = self._response_times[-1000:]
        
        # Пересчитываем среднее
        if self._response_times:
            self.avg_response_time_ms = sum(self._response_times) / len(self._response_times)
    
    def get_summary(self) -> Dict[str, Any]:
        """Получить сводку метрик."""
        return {
            "uptime": self.uptime_formatted,
            "uptime_seconds": int(self.uptime_seconds),
            "requests": {
                "messages": self.messages_received,
                "callbacks": self.callbacks_received,
                "commands": self.commands_executed,
                "total": self.messages_received + self.callbacks_received,
            },
            "generations": {
                "started": self.generations_started,
                "completed": self.generations_completed,
                "failed": self.generations_failed,
                "success_rate": round(
                    self.generations_completed / max(self.generations_started, 1) * 100, 1
                ),
            },
            "payments": {
                "completed": self.payments_completed,
                "failed": self.payments_failed,
                "revenue_rub": self.total_revenue_kopecks / 100,
            },
            "errors": {
                "total": self.errors_total,
                "by_type": self.errors_by_type,
            },
            "performance": {
                "avg_response_time_ms": round(self.avg_response_time_ms, 2),
            },
        }
    
    def reset(self):
        """Сбросить метрики (сохраняя время старта)."""
        self.messages_received = 0
        self.callbacks_received = 0
        self.commands_executed = 0
        self.generations_started = 0
        self.generations_completed = 0
        self.generations_failed = 0
        self.payments_initiated = 0
        self.payments_completed = 0
        self.payments_failed = 0
        self.errors_total = 0
        self.errors_by_type.clear()
        self._response_times.clear()
        self.avg_response_time_ms = 0.0


# Глобальный объект метрик
metrics = BotMetrics()


# ============================================================
# HEALTH CHECK
# ============================================================

@dataclass
class HealthStatus:
    """Статус здоровья компонента."""
    
    name: str
    status: str  # "healthy", "degraded", "unhealthy"
    latency_ms: Optional[float] = None
    message: Optional[str] = None
    last_check: float = field(default_factory=time.time)


async def check_database_health() -> HealthStatus:
    """Проверка здоровья базы данных."""
    from database.database import health_check
    
    try:
        result = await health_check()
        
        if result["status"] == "healthy":
            return HealthStatus(
                name="database",
                status="healthy",
                latency_ms=result["latency_ms"],
            )
        else:
            return HealthStatus(
                name="database",
                status="unhealthy",
                message=result.get("error"),
            )
    except Exception as e:
        return HealthStatus(
            name="database",
            status="unhealthy",
            message=str(e),
        )


async def check_ai_provider_health() -> HealthStatus:
    """Проверка здоровья AI провайдера."""
    try:
        # Простая проверка - есть ли API ключ
        if settings.gemini_api_key:
            return HealthStatus(
                name="ai_provider",
                status="healthy",
                message="Gemini API key configured",
            )
        else:
            return HealthStatus(
                name="ai_provider",
                status="degraded",
                message="No AI provider configured",
            )
    except Exception as e:
        return HealthStatus(
            name="ai_provider",
            status="unhealthy",
            message=str(e),
        )


async def get_full_health_status() -> Dict[str, Any]:
    """
    Получить полный статус здоровья системы.
    
    Returns:
        Словарь со статусами всех компонентов
    """
    checks = await asyncio.gather(
        check_database_health(),
        check_ai_provider_health(),
        return_exceptions=True,
    )
    
    components = {}
    overall_status = "healthy"
    
    for check in checks:
        if isinstance(check, BaseException):
            components["unknown"] = {
                "status": "unhealthy",
                "error": str(check),
            }
            overall_status = "unhealthy"
        elif isinstance(check, HealthStatus):
            components[check.name] = {
                "status": check.status,
                "latency_ms": check.latency_ms,
                "message": check.message,
            }
            
            if check.status == "unhealthy":
                overall_status = "unhealthy"
            elif check.status == "degraded" and overall_status == "healthy":
                overall_status = "degraded"
    
    return {
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "uptime": metrics.uptime_formatted,
        "components": components,
    }


# ============================================================
# АЛЕРТЫ
# ============================================================

class AlertManager:
    """Менеджер алертов."""
    
    def __init__(self):
        self.alerts: List[Dict[str, Any]] = []
        self.alert_callbacks = []
    
    async def check_thresholds(self):
        """Проверить пороговые значения и создать алерты."""
        
        # Проверка error rate
        if metrics.errors_total > 0:
            error_rate = metrics.errors_total / max(
                metrics.messages_received + metrics.callbacks_received, 1
            )
            if error_rate > 0.1:  # > 10% ошибок
                await self.create_alert(
                    "high_error_rate",
                    f"Error rate: {error_rate*100:.1f}%",
                    severity="warning",
                )
        
        # Проверка времени ответа
        if metrics.avg_response_time_ms > 5000:  # > 5 секунд
            await self.create_alert(
                "slow_response",
                f"Avg response time: {metrics.avg_response_time_ms:.0f}ms",
                severity="warning",
            )
        
        # Проверка generation failure rate
        if metrics.generations_started > 10:
            fail_rate = metrics.generations_failed / metrics.generations_started
            if fail_rate > 0.2:  # > 20% неудач
                await self.create_alert(
                    "high_generation_failure_rate",
                    f"Generation failure rate: {fail_rate*100:.1f}%",
                    severity="critical",
                )
    
    async def create_alert(
        self,
        alert_type: str,
        message: str,
        severity: str = "info",
    ):
        """Создать алерт."""
        alert = {
            "type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": datetime.now().isoformat(),
        }
        
        self.alerts.append(alert)
        
        # Храним только последние 100 алертов
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
        
        logger.warning(
            "alert_created",
            alert_type=alert_type,
            message=message,
            severity=severity,
        )
        
        # Вызываем callbacks (для уведомлений)
        for callback in self.alert_callbacks:
            try:
                await callback(alert)
            except Exception as e:
                logger.error("alert_callback_failed", error=str(e))
    
    def get_recent_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Получить алерты за последние N часов."""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        return [
            a for a in self.alerts
            if datetime.fromisoformat(a["timestamp"]) > cutoff
        ]
    
    def register_callback(self, callback):
        """Зарегистрировать callback для алертов."""
        self.alert_callbacks.append(callback)


# Глобальный менеджер алертов
alert_manager = AlertManager()


# ============================================================
# DASHBOARD API
# ============================================================

async def get_dashboard_data() -> Dict[str, Any]:
    """
    Получить все данные для дашборда мониторинга.
    
    Returns:
        Полный набор данных для отображения
    """
    health = await get_full_health_status()
    
    return {
        "health": health,
        "metrics": metrics.get_summary(),
        "alerts": alert_manager.get_recent_alerts(hours=24),
        "timestamp": datetime.now().isoformat(),
    }
