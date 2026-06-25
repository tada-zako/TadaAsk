from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlsplit, urlunparse

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


def normalize_origin(value: str) -> str:
    """
    标准化浏览器携带的 origin 字段；
    用于跨域请求的来源验证，确保 origin 是一个合法的绝对 URL

    标准化包括：
    - 协议，主机名转换为小写
    - 移除默认端口（http:80, https:443）
    - IPv6 地址使用方括号包裹
    - 移除路径、查询参数和 fragment
    """
    parsed = urlsplit(value.strip())
    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower() if parsed.hostname else ""

    if scheme not in {"http", "https"} or not hostname:
        # origin 必须是 http(s) URL
        raise ValueError("origin must be an absolute http(s) URL")

    # 解析 port，移除默认端口
    port = parsed.port
    default_port = (scheme == "http" and port == 80) or (
        scheme == "https" and port == 443
    )
    # 确保 IPv6 地址使用方括号包裹
    host = (
        f"[{hostname}]"
        if ":" in hostname and not hostname.startswith("[")
        else hostname
    )
    port_part = f":{port}" if port and not default_port else ""
    return f"{scheme}://{host}{port_part}"
