import time
import threading
from collections import OrderedDict
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class TTLCache(Generic[K, V]):
    """
    带线程锁的 TTL 缓存实现；
    基于 OrderedDict 实现 LRU 淘汰策略 + 绝对过期的 TTL 机制；
    """

    def __init__(self, *, max_size: int = 512, ttl_seconds: int = 1800):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._items: OrderedDict[K, tuple[float, V]] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: K) -> V | None:
        now = time.monotonic()

        # 获取锁，确保线程安全
        with self._lock:
            item = self._items.get(key)

            if item is None:
                return None

            created_at, value = item
            if now - created_at > self.ttl_seconds:
                self._items.pop(key, None)
                return None

            # 移动 item 到末尾；保持 LRU 顺序
            self._items.move_to_end(key)
            return value

    def set(self, key: K, value: V) -> None:
        now = time.monotonic()

        with self._lock:
            self._items[key] = (now, value)
            self._items.move_to_end(key)

            # 超过 max_size 时，基于 LRU 策略淘汰最旧的 item
            while len(self._items) > self.max_size:
                self._items.popitem(last=False)

    def delete(self, key: K) -> None:
        with self._lock:
            self._items.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
