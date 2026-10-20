"""웹사이트 대표 아이콘(파비콘) 가져오기 + 보관.

 · 가져오기(fetch)는 표준 라이브러리만 쓰고 nethelper 보조 프로세스 안에서 한다 (본체 메모리를 아끼려고).
   사이트의 첫 화면(HTML)에서 <link rel="icon">·apple-touch-icon 을 찾아 가장 큰 그림을 받고, 없으면 /favicon.ico 를 받는다.
 · 받은 그림은 데이터폴더\\icons\\사이트주소.img 에 원본 그대로 둔다 (실패하면 .none 표식을 남겨 3일 동안 다시 시도하지 않는다).
 · 본체는 런처를 열 때만 그림 파일을 읽어서(load) 귀여운 스티커에 넣는다.
"""
import base64
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DesktopCat/1.0"}
RETRY_AFTER = 3 * 24 * 3600


def _host(url: str) -> str:
    h = urllib.parse.urlparse(url if "://" in url else "https://" + url).hostname or ""
    return re.sub(r"[^a-z0-9.\-]", "_", h.lower())


def cache_file(icons_dir, url: str) -> Path:
    return Path(icons_dir) / (_host(url) + ".img")


def need(icons_dir, url: str) -> bool:
    """아직 가져오지 않았고 최근에 실패하지도 않았으면 True."""
    h = _host(url)
    if not h:
        return False
    d = Path(icons_dir)
    if (d / (h + ".img")).exists():
        return False
    none = d / (h + ".none")
    try:
        return not (none.exists() and time.time() - none.stat().st_mtime < RETRY_AFTER)
    except OSError:
        return True


def load(icons_dir, url: str):
    """보관된 파비콘을 QPixmap 으로 (없거나 읽을 수 없으면 None). 본체(화면 스레드)에서 부른다.
    .ico 처럼 여러 크기가 한 파일에 들어 있으면 가장 큰 그림을 쓴다."""
    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
    from PyQt6.QtGui import QImage, QImageReader, QPixmap
    f = cache_file(icons_dir, url)
    try:
        if not f.exists():
            return None
        buf = QBuffer()
        buf.setData(QByteArray(f.read_bytes()))
        buf.open(QIODevice.OpenModeFlag.ReadOnly)
        rd = QImageReader(buf)
        best = None
        for i in range(max(1, min(rd.imageCount(), 12))):
            if rd.jumpToImage(i):
                img = rd.read()
                if not img.isNull() and (best is None or img.width() > best.width()):
                    best = img
            if rd.imageCount() <= 1:
                break
        if best is None:
            pm = QPixmap()
            return pm if pm.loadFromData(f.read_bytes()) and not pm.isNull() else None
        return QPixmap.fromImage(best)
    except OSError:
        return None


# ---------------------------------------------------------------- 보조 프로세스 쪽
def _get(url: str, limit: int, timeout: float = 8.0):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(limit), (r.headers.get("Content-Type") or "").lower(), r.geturl()


def _is_image(b: bytes) -> bool:
    """PNG / ICO / JPEG / GIF / WEBP 인가 (SVG 는 쓰지 않는다)."""
    return (b[:8] == b"\x89PNG\r\n\x1a\n" or b[:4] == b"\x00\x00\x01\x00" or b[:3] == b"\xff\xd8\xff" or b[:4] == b"GIF8"
            or (b[:4] == b"RIFF" and b[8:12] == b"WEBP"))


def _candidates(html: str, base: str):
    out = []
    for tag in re.findall(r"<link\b[^>]*>", html, flags=re.I)[:60]:
        rel = re.search(r"rel\s*=\s*[\"']([^\"']*)[\"']", tag, flags=re.I)
        href = re.search(r"href\s*=\s*[\"']([^\"']+)[\"']", tag, flags=re.I)
        if not rel or not href or "icon" not in rel.group(1).lower():
            continue
        url = urllib.parse.urljoin(base, href.group(1).strip())
        if url.lower().split("?")[0].endswith(".svg") or "svg" in (re.search(r"type\s*=\s*[\"']([^\"']*)", tag, flags=re.I) or [None, ""])[1]:
            continue
        size = 32 if "apple" not in rel.group(1).lower() else 180
        m = re.search(r"sizes\s*=\s*[\"'](\d+)x\d+", tag, flags=re.I)
        if m:
            size = int(m.group(1))
        out.append((min(size, 256) if size <= 256 else 256, url))
    out.sort(key=lambda x: -x[0])
    return [u for _, u in out]


def _bases(p):
    """시도할 주소들: 그대로(https) → 'www.' 를 붙여서 → http. (예: naver.com 은 인증서가 맞지 않아 www.naver.com 으로 가야 열린다)"""
    host = p.netloc
    out = ["https://%s/" % host]
    if not host.lower().startswith("www.") and host.count(".") == 1:
        out.append("https://www.%s/" % host)
    out.append("http://%s/" % host)
    return out


def _fetch_from(base: str):
    cands = []
    try:
        data, _ct, final = _get(base, 400000)
        cands += _candidates(data.decode("utf-8", "replace"), final)
        root = urllib.parse.urljoin(final, "/")
    except Exception:
        root = base
    cands.append(urllib.parse.urljoin(root, "/favicon.ico"))
    for u in cands[:4]:
        try:
            b, _ct, _f = _get(u, 300000)
        except Exception:
            continue
        if len(b) > 60 and _is_image(b):
            return b
    return None


def fetch(page_url: str):
    """사이트의 파비콘 원본 바이트. 못 찾으면 None."""
    if "://" not in page_url:
        page_url = "https://" + page_url
    p = urllib.parse.urlparse(page_url)
    if not p.hostname:
        return None
    for base in _bases(p):
        b = _fetch_from(base)
        if b:
            return b
    return None


def fetch_b64(page_url: str) -> str:
    b = fetch(page_url)
    return base64.b64encode(b).decode("ascii") if b else ""


# ---------------------------------------------------------------- 본체 쪽 (작업 스레드에서 부른다)
def fetch_to_cache(icons_dir, url: str, call) -> bool:
    """call: nethelper.call. 받아서 보관한다. 실패하면 .none 표식을 남긴다."""
    d = Path(icons_dir)
    h = _host(url)
    try:
        d.mkdir(parents=True, exist_ok=True)
        res = call("favicon", url=url)
        b = base64.b64decode(res.get("b64", "")) if res else b""
        if b and _is_image(b):
            tmp = d / (h + ".tmp")
            tmp.write_bytes(b)
            tmp.replace(d / (h + ".img"))
            return True
        (d / (h + ".none")).write_text(str(int(time.time())), encoding="utf-8")
    except Exception:
        try:
            (d / (h + ".none")).write_text(str(int(time.time())), encoding="utf-8")
        except OSError:
            pass
    return False
