"""AIGateway: única puerta hacia la IA (ADR-07).

privacidad → prompt versionado → (deshabilitada / breaker) → llamada con presupuesto y como máximo
1 reintento → parseo + reglas → métrica en ai_call_logs. Nunca guarda ni registra prompt ni respuesta.
"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Generic, Protocol, TypeVar

from pydantic import BaseModel

from app.ai.call_log import CallLogEntry, CallRecorder, DbCallRecorder
from app.ai.errors import AIFailure, AIInvalidOutput, AIProviderError, CallStatus
from app.ai.ports import TextGenerator, TextRequest
from app.ai.privacy import PrivacyGuard
from app.ai.registry import PromptRegistry, get_prompt_registry
from app.ai.resilience import RETRY_BACKOFF_SECONDS, CircuitBreaker, SleepFn, TimeFn, real_sleep
from app.core.clock import Clock
from app.core.config import Settings, get_settings
from app.core.db import get_sessionmaker

logger = logging.getLogger("fitia.ai")

T = TypeVar("T")
I = TypeVar("I", bound=BaseModel)

CODE_UNAVAILABLE = "AI_UNAVAILABLE"
CODE_INVALID_OUTPUT = "AI_INVALID_OUTPUT"
CODE_TIMEOUT = "GENERATION_TIMEOUT"


class UseCase(Protocol[I, T]):
    name: str
    allowed_keys: frozenset[str]

    def parse(self, text: str, payload: I) -> T: ...


@dataclass(frozen=True)
class AIResult(Generic[T]):
    value: T
    attempts: int
    latency_ms: int
    prompt_version: str
    model: str


class AIGateway:
    def __init__(
        self,
        settings: Settings,
        generator: TextGenerator,
        breaker: CircuitBreaker,
        recorder: CallRecorder,
        clock: Clock,
        registry: PromptRegistry | None = None,
        time_fn: TimeFn = time.monotonic,
        sleep: SleepFn = real_sleep,
    ) -> None:
        self._settings = settings
        self._generator = generator
        self.breaker = breaker
        self._recorder = recorder
        self._clock = clock
        self._registry = registry or get_prompt_registry()
        self._time = time_fn
        self._sleep = sleep

    def prompt_version(self, use_case: UseCase[Any, Any]) -> str:
        versions = {"weekly_plan": self._settings.PROMPT_VERSION_WEEKLY_PLAN}
        return versions[use_case.name]

    async def run(self, use_case: UseCase[I, T], payload: I) -> AIResult[T]:
        input_data = PrivacyGuard(use_case.allowed_keys).build(payload.model_dump())
        version = self.prompt_version(use_case)
        spec = self._registry.load(use_case.name, version)
        model = self._settings.GEMINI_MODEL or spec.model
        logged_model = self._generator.model_name or model
        # La entrada va como DATOS entre delimitadores dentro de la plantilla, nunca como instrucciones.
        prompt = spec.render(json.dumps(input_data, ensure_ascii=False, sort_keys=True))

        started = self._time()
        attempts = 0

        async def finish(status: CallStatus) -> int:
            latency_ms = int((self._time() - started) * 1000)
            await self._recorder.record(
                CallLogEntry(
                    use_case=use_case.name,
                    prompt_version=version,
                    model=logged_model,
                    status=status,
                    latency_ms=latency_ms,
                    attempts=attempts,
                    created_at=self._clock.now(),
                )
            )
            return latency_ms

        if not self._settings.AI_ENABLED:
            raise AIFailure(CODE_UNAVAILABLE, "disabled", latency_ms=await finish("disabled"))

        budget = self._settings.AI_TOTAL_BUDGET_SECONDS
        while True:
            if not self.breaker.allow():
                raise AIFailure(
                    CODE_UNAVAILABLE, "breaker_open", attempts=attempts, latency_ms=await finish("breaker_open")
                )
            remaining = budget - (self._time() - started)
            timeout = max(0.1, min(self._settings.AI_TIMEOUT_SECONDS, remaining))
            attempts += 1
            request = TextRequest(
                system=spec.system,
                prompt=prompt,
                input_data=input_data,
                response_schema=spec.output_schema,
                temperature=spec.temperature,
                max_output_tokens=spec.max_output_tokens,
                timeout_seconds=timeout,
                model=model,
                thinking_level=spec.thinking_level,
            )
            try:
                try:
                    text = await asyncio.wait_for(self._generator.generate(request), timeout)
                except TimeoutError as exc:
                    raise AIProviderError("timeout") from exc
                self.breaker.record_success()  # el proveedor respondió: está disponible
                value = use_case.parse(text, payload)
                latency_ms = await finish("ok")
                return AIResult(value=value, attempts=attempts, latency_ms=latency_ms, prompt_version=version, model=logged_model)
            except AIProviderError as exc:
                # Todo error del proveedor es de DISPONIBILIDAD y cuenta para el breaker.
                self.breaker.record_failure()
                kind = exc.kind
                code = CODE_TIMEOUT if kind == "timeout" else CODE_UNAVAILABLE
                status: CallStatus = "timeout" if kind == "timeout" else "provider_error"
            except AIInvalidOutput:
                # Problema de calidad, no de disponibilidad: NO cuenta como fallo para el breaker
                # (y, si era el intento de prueba, el proveedor sí respondió).
                self.breaker.record_success()
                kind = "invalid_output"
                code, status = CODE_INVALID_OUTPUT, "invalid_output"

            elapsed = self._time() - started
            can_retry = (
                kind in spec.retry_on
                and attempts <= spec.max_retries
                and budget - elapsed - RETRY_BACKOFF_SECONDS >= self._settings.AI_RETRY_MIN_REMAINING_SECONDS
            )
            if not can_retry:
                raise AIFailure(code, status, attempts=attempts, latency_ms=await finish(status))
            logger.info("ai_retry", extra={"use_case": use_case.name, "reason": kind})
            await self._sleep(RETRY_BACKOFF_SECONDS)


_gateway: AIGateway | None = None


def build_generator(settings: Settings) -> TextGenerator:
    if settings.AI_PROVIDER == "gemini":
        from app.ai.adapters.gemini_text import GeminiTextAdapter

        return GeminiTextAdapter(api_key=settings.GEMINI_API_KEY)
    from app.ai.adapters.fake_text import FakeTextAdapter

    return FakeTextAdapter()


def get_ai_gateway() -> AIGateway:
    """Una instancia por proceso: el breaker debe ser compartido por todas las peticiones."""
    global _gateway
    if _gateway is None:
        settings = get_settings()
        _gateway = AIGateway(
            settings=settings,
            generator=build_generator(settings),
            breaker=CircuitBreaker(
                settings.AI_BREAKER_FAILURES, settings.AI_BREAKER_WINDOW_SECONDS, settings.AI_BREAKER_OPEN_SECONDS
            ),
            recorder=DbCallRecorder(get_sessionmaker()),
            clock=Clock(),
        )
    return _gateway
