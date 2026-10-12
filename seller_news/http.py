import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
TIMEOUT = 20


def make_session(proxy: str = "system") -> requests.Session:
    """proxy: "system" — системный прокси, "direct" — без прокси, иначе URL прокси."""
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ru-RU,ru;q=0.9"})
    if proxy == "direct":
        s.trust_env = False
    elif proxy != "system":
        s.trust_env = False
        s.proxies = {"http": proxy, "https": proxy}
    return s


def get(session: requests.Session, url: str, **kwargs) -> requests.Response:
    r = session.get(url, timeout=TIMEOUT, **kwargs)
    r.raise_for_status()
    return r
