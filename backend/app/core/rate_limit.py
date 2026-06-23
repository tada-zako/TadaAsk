from collections import deque
import asyncio
import time
from dataclasses import dataclass
from math import ceil

from .exceptions import VisitorRateLimitError


@dataclass
class VisitorStreamLease:
    """visitor 侧 stream 租约；
    记录 stream 的持有信息"""

    ip: str
    project_uid: str


class VisitorRateLimiter:
    """visitor 侧请求限流器"""

    def __init__(
        self,
        *,
        enabled: bool,
        ip_project_per_minute: int,
        ip_project_per_hour: int,
        ip_per_minute: int,
        project_per_minute: int,
        stream_per_ip: int,
        stream_per_project: int,
    ):
        self.enabled = enabled
        # 请求限流
        self.ip_project_per_minute = ip_project_per_minute
        self.ip_project_per_hour = ip_project_per_hour
        self.ip_per_minute = ip_per_minute
        self.project_per_minute = project_per_minute
        # stream 限流
        self.stream_per_ip = stream_per_ip
        self.stream_per_project = stream_per_project

        # 计数变量
        self._active_ip: dict[str, int] = {}  # 每个 IP 持有 stream 数量
        self._active_project: dict[str, int] = {}  # 每个 project 持有 stream 数量
        self._hits: dict[str, deque[float]] = {}  # 请求规则 -> 请求时间戳
        self._lock = asyncio.Lock()  # 异步锁，确保并发安全

        # 定器清理 _hits 中过期的请求记录
        self._cleanup_interval = 600  # 每 10 分钟清理一次过期请求记录
        self._max_window = 3600  # 最大请求记录保留时间窗口
        self._last_cleanup_time = time.monotonic()  # 上一次清理的时间戳

    async def check_request(self, *, ip: str, project_uid: str) -> None:
        """
        检查 visitor 请求是否超过限流阈值
        """
        if not self.enabled:
            return

        async with self._lock:
            now = time.monotonic()

            if now - self._last_cleanup_time > self._cleanup_interval:
                # 到达清理间隔
                self._cleanup_expired(now)

            # 组装限流检查规则
            checks = [
                # key(rule:window:ip:project_uid), window in seconds, limit
                (f"ip_project:1m:{ip}:{project_uid}", 60, self.ip_project_per_minute),
                (f"ip_project:1h:{ip}:{project_uid}", 3600, self.ip_project_per_hour),
                (f"ip:1m:{ip}", 60, self.ip_per_minute),
                (f"project:1m:{project_uid}", 60, self.project_per_minute),
            ]

            for key, window, limit in checks:
                self._check_window(key=key, window=window, limit=limit, now=now)

    async def acquire_stream(self, *, ip: str, project_uid: str) -> VisitorStreamLease:
        """
        尝试获取 visitor stream lease
        """
        if not self.enabled:
            return VisitorStreamLease(ip=ip, project_uid=project_uid)

        async with self._lock:
            # 检查 IP 限流
            ip_count = self._active_ip.get(ip, 0)
            if ip_count >= self.stream_per_ip:
                raise VisitorRateLimitError(
                    retry_after_seconds=10,
                    message="Too many active visitor chat streams, please retry later.",
                )

            # 检查 project 限流
            project_count = self._active_project.get(project_uid, 0)
            if project_count >= self.stream_per_project:
                raise VisitorRateLimitError(
                    retry_after_seconds=10,
                    message="Too many active visitor chat streams, please retry later.",
                )

            # 获取租约
            self._active_ip[ip] = ip_count + 1
            self._active_project[project_uid] = project_count + 1

        return VisitorStreamLease(ip=ip, project_uid=project_uid)

    async def release_stream(self, lease: VisitorStreamLease) -> None:
        """释放 visitor stream lease"""
        if not self.enabled:
            return

        # 释放租约
        async with self._lock:
            self._decrement(self._active_ip, lease.ip)
            self._decrement(self._active_project, lease.project_uid)

    def _cleanup_expired(self, now: float) -> None:
        """
        清理过期的请求记录，避免某个 IP 访问后长期不访问；
        清理规则: MVP 阶段，简单实现为清理存在时长超过 _max_window 的请求记录；
        """
        expires_before = now - self._max_window

        # 清理 _hits 中过期的请求记录
        expired_keys = [
            key
            for key, hits in self._hits.items()
            if not hits or hits[-1] < expires_before
        ]
        for key in expired_keys:
            self._hits.pop(key, None)

        # 更新最后清理时间
        self._last_cleanup_time = now

    def _check_window(self, *, key: str, window: int, limit: int, now: float) -> None:
        """
        判断当前请求是否超出限流阈值
        """
        if limit <= 0:
            return

        hits = self._hits.get(key)
        if hits is None:
            hits = deque()
            self._hits[key] = hits

        # 移除过期的请求记录
        expires_before = now - window
        while hits and hits[0] < expires_before:
            hits.popleft()

        # 检查当前请求是否超过限流阈值
        if len(hits) >= limit:
            # 超过限流阈值，抛出异常
            retry_after_seconds = ceil(hits[0] + window - now)
            raise VisitorRateLimitError(
                retry_after_seconds=max(1, retry_after_seconds),
                message="Too many visitor requests, please retry later.",
            )

        # 记录当前请求
        hits.append(now)

    @staticmethod
    def _decrement(counter: dict[str, int], key: str) -> None:
        """工具函数：将计数器中指定 key 的值减 1，如果减到 0，则删除该 key"""
        value = counter.get(key, 0)
        if value <= 1:
            counter.pop(key, None)
        else:
            counter[key] = value - 1
