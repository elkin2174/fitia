"""Caché en memoria de audios con algoritmo LRU y control de un solo vuelo (single-flight) (HU 2).

- Clave: SHA-256 de (modelo + ":" + voz + ":" + texto).
- Almacenamiento: memoria de proceso (OrderedDict) acotada a un número máximo de entradas (LRU).
- Single-flight: si múltiples solicitudes concurrentes piden el mismo audio no cacheado,
  solo una ejecuta la llamada y las demás esperan su resultado mediante un asyncio.Future.
- Persistencia: NUNCA se persiste en base de datos. La caché es local al proceso y se pierde al reiniciar.
"""
import asyncio
from collections import OrderedDict
from collections.abc import Awaitable, Callable
import hashlib
import logging

logger = logging.getLogger("fitia.ai.audio_cache")

DEFAULT_CACHE_MAX_ENTRIES = 128


def make_cache_key(model: str, voice: str, text: str) -> str:
    """Genera una clave SHA-256 única y determinista para la combinación modelo + voz + texto."""
    payload = f"{model}:{voice}:{text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class AudioCache:
    def __init__(self, max_entries: int = DEFAULT_CACHE_MAX_ENTRIES) -> None:
        self.max_entries = max_entries
        self._entries: OrderedDict[str, bytes] = OrderedDict()
        self._in_flight: dict[str, asyncio.Future[bytes]] = {}
        self._lock = asyncio.Lock()

    def get(self, key: str) -> bytes | None:
        """Obtiene un audio de la caché si existe, actualizando su posición LRU."""
        if key in self._entries:
            self._entries.move_to_end(key)
            return self._entries[key]
        return None

    def set(self, key: str, value: bytes) -> None:
        """Guarda un audio en la caché, desalojando la entrada más antigua si supera la capacidad."""
        if key in self._entries:
            self._entries.move_to_end(key)
        self._entries[key] = value
        if len(self._entries) > self.max_entries:
            evicted_key, _ = self._entries.popitem(last=False)
            logger.debug("audio_cache_evicted", extra={"key": evicted_key})

    async def get_or_compute(self, key: str, compute_fn: Callable[[], Awaitable[bytes]]) -> bytes:
        """Single-flight pattern: si ya está en caché, retorna de inmediato.

        Si ya hay un cómputo en curso para la misma clave, espera el mismo Future.
        Si es la primera en llegar, ejecuta compute_fn(), resuelve el Future para los concurrentes
        y almacena el resultado en la caché LRU.
        """
        # 1. Comprobación rápida en caché
        cached = self.get(key)
        if cached is not None:
            return cached

        # 2. Coordinación single-flight con lock
        async with self._lock:
            # Recomprobar por si otra corrutina terminó mientras esperábamos el lock
            cached = self.get(key)
            if cached is not None:
                return cached

            # Si ya hay una generación en curso para esta clave, nos acoplamos a su Future
            if key in self._in_flight:
                future = self._in_flight[key]
                is_leader = False
            else:
                loop = asyncio.get_running_loop()
                future = loop.create_future()
                self._in_flight[key] = future
                is_leader = True

        if not is_leader:
            # Esperar a que el líder complete la generación
            return await future

        # 3. El líder ejecuta el cómputo real
        try:
            result = await compute_fn()
            # Guardar en caché LRU
            self.set(key, result)
            # Notificar a los seguidores
            future.set_result(result)
            return result
        except BaseException as exc:
            # Propagar la excepción a todos los concurrentes
            future.set_exception(exc)
            raise
        finally:
            async with self._lock:
                self._in_flight.pop(key, None)
            if future.done() and not future.cancelled():
                # Marcar la excepción como recuperada si ningún seguidor concurrente la consumió
                future.exception()

    def clear(self) -> None:
        """Limpia la caché en memoria (usado principalmente en pruebas)."""
        self._entries.clear()
        self._in_flight.clear()

    def size(self) -> int:
        return len(self._entries)


_audio_cache = AudioCache()


def get_audio_cache() -> AudioCache:
    """Instancia singleton de la caché de audio en memoria para el proceso."""
    return _audio_cache
