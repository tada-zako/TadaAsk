from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "msclkid"}


def normalize_url(url: str, *, base_url: str | None = None) -> str:
    """
    规范化 URL

    规范化包括：
    - 解析 URL 并确保 scheme 是 http 或 https
    - 移除 URL 中的跟踪参数（如 utm_*, fbclid, gclid 等）
    - 统一 scheme 和 host 的大小写为小写
    - 移除 URL 中的 fragment 部分
    """
    if base_url:
        url = urljoin(base_url, url)

    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")

    # 移除跟踪参数
    query_items = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key in TRACKING_QUERY_KEYS or key.startswith(TRACKING_QUERY_PREFIXES):
            continue
        query_items.append((key, value))

    path = parsed.path or "/"
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        path=path,
        query=urlencode(query_items, doseq=True),
        fragment="",
    )
    return urlunparse(normalized)


def hostname_from_url(url: str) -> str:
    """从 URL 中提取 hostname"""
    return urlparse(str(url)).hostname or ""


def path_prefix_from_url(url: str) -> str:
    """
    从 URL 中提取路径前缀；
    NOTE: 返回的结果会自动在路径结尾补全 "/"
    """
    path = urlparse(str(url)).path or "/"
    if not path.endswith("/"):
        path = path + "/"
    return path
