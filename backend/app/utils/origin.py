from urllib.parse import urlsplit


def normalize_origin(value: str) -> str:
    """Return a canonical browser origin: scheme://host[:port]."""
    parsed = urlsplit(value.strip())
    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower() if parsed.hostname else ""

    if scheme not in {"http", "https"} or not hostname:
        raise ValueError("origin must be an absolute http(s) URL")

    port = parsed.port
    default_port = (scheme == "http" and port == 80) or (
        scheme == "https" and port == 443
    )
    host = f"[{hostname}]" if ":" in hostname and not hostname.startswith("[") else hostname
    port_part = f":{port}" if port and not default_port else ""
    return f"{scheme}://{host}{port_part}"


def origins_match(left: str, right: str) -> bool:
    return normalize_origin(left) == normalize_origin(right)
