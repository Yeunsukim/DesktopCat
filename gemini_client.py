"""Google Gemini API 호출 (표준 라이브러리만 사용, nethelper 보조 프로세스 안에서 실행된다).

공식 문서(ai.google.dev/gemini-api/docs)에서 확인한 형식:
 · 기본: Interactions API  POST https://generativelanguage.googleapis.com/v1beta/interactions
     헤더 x-goog-api-key, 본문 {"model", "input", "system_instruction", "tools": [{"type": "google_search"}], "store": false}
     답: steps[] 중 type == "model_output" 의 content[] 안 type == "text" 의 text, 출처는 text 의 annotations 중 url_citation(url, title)
 · 되돌림: 위 주소가 404/405 면 기존 generateContent(/v1beta/models/{model}:generateContent)로 한 번 더 시도한다. 문서가 두 곳에서 주소를
   다르게 적고 있어서(그리고 generateContent 도 계속 지원한다고 함), 둘 다 쓸 수 있게 해 두었다.
 · 오류: HTTP 상태 + {"error": {"code": "rate_limit_exceeded", "message": ...}}. 429/503/5xx 는 잠깐 쉬었다 다시 시도(최대 2번).
API 키는 헤더로만 보내고, 오류 메시지·로그에는 절대 넣지 않는다.
"""
import json
import os
import time

DEFAULT_MODEL = "gemini-3.5-flash-lite"            # 문서가 '빠르고 싼 기본값'으로 안내하는 안정(Stable) 모델. 설정에서 바꿀 수 있다
BASE = "https://generativelanguage.googleapis.com/v1beta"
_override = os.environ.get("DESKTOPCAT_GEMINI_BASE", "")
if _override.startswith("http://127.0.0.1"):          # 시험용: 이 컴퓨터의 가짜 서버로만 돌릴 수 있다 (키가 다른 곳으로 새지 않게 127.0.0.1 만 허용)
    BASE = _override
RETRY_DELAYS = (3, 8)                                # 일시적 오류일 때 다시 시도하기 전에 쉬는 초 (시험에서는 줄인다)

SYSTEM = ("너는 사용자의 바탕화면에 사는 고양이 비서야. 한국어로, 짧고 읽기 쉬운 Markdown(제목, 불릿)으로 답해. "
          "모든 문장은 '~냥' 또는 '~옹'으로 끝내(예: 맑다냥, 우산을 챙겨라옹, 올랐다냥). 숫자·고유명사는 그대로 쓰고 군더더기 인사는 생략해. "
          "주어진 자료나 확인한 사실만 쓰고, 모르는 것은 지어내지 말고 '확인 못 했다냥'이라고 해. "
          "주식·환율은 숫자를 전달할 뿐 투자 조언은 하지 마.")

# 뉴스·날씨·주식처럼 '밖에서 가져온 정보'를 정리할 때는 고양이 말투 없이 담백한 존댓말로 쓴다 (정보를 흐리지 않게)
SYSTEM_PLAIN = ("너는 사용자의 바탕화면에 사는 비서야. 한국어로, 짧고 읽기 쉬운 Markdown(제목, 불릿)으로 답해. "
                "말투는 담백한 존댓말(~입니다, ~예요)로 하고 '~냥', '~옹' 같은 고양이 말투와 이모티콘은 쓰지 마. 군더더기 인사는 생략해. "
                "주어진 자료만 근거로 쓰고, 모르는 것은 지어내지 말고 '확인하지 못했습니다'라고 해. "
                "주식·환율은 숫자를 전달할 뿐 투자 조언은 하지 마.")

# 날씨·뉴스·시세 자료는 고양이가 직접 모아서 이 프롬프트 뒤에 붙여 보낸다 (무료 등급에서는 Gemini 의 구글 검색 도구가 막혀 있다)
DEFAULT_NEWS_PROMPT = ("아래 자료로 오늘의 소식을 정리해 줘.\n"
                       "1. 날씨 (기온, 강수 확률, 옷차림 한 줄)\n"
                       "2. 주요 뉴스 5개 (자료에서 골라 각 한 줄, 언론사 이름 포함)\n"
                       "3. 시세 (지수·환율마다 등락을 한 줄씩)\n"
                       "전체 25줄 이내로 간단히.")


DEFAULT_YESTERDAY_PROMPT = ("아래는 컴퓨터에서 쓴 프로그램과 창 제목 기록이야. 이 날 무엇을 했는지 정리해 줘.\n"
                            "1. 한 일 요약 (3~5줄)\n"
                            "2. 많이 쓴 프로그램 순위 (시간 포함, 상위 5개)\n"
                            "3. 눈에 띄는 작업이나 패턴 한두 줄\n"
                            "창 제목만 보고 짐작하는 거니까 확실하지 않은 건 단정하지 말고, 전체 20줄 이내로 간단히.")


class GeminiError(Exception):
    """사용자에게 그대로 보여 줄 한국어 메시지. retry=True 면 잠시 뒤 다시 해 볼 만한 오류."""

    def __init__(self, message, retry=False):
        super().__init__(message)
        self.retry = retry


# 오류 코드 → (사용자 메시지, 다시 해 볼 만한가)
_MESSAGES = {
    "authentication": ("Gemini 키가 틀렸거나 만료됐다냥 (설정 → 소식에서 키를 다시 확인해 달라옹)", False),
    "permission_denied": ("이 키로는 쓸 수 없다냥 (키 권한이나 지역 제한을 확인해 달라옹)", False),
    "model_not_found": ("모델 이름을 못 찾겠다냥 (설정 → 소식에서 모델 이름을 확인해 달라옹)", False),
    "not_found": ("요청한 주소나 모델을 못 찾겠다냥", False),
    "payment_required": ("Gemini 크레딧이 모자라다냥 (결제·크레딧을 확인해 달라옹)", False),
    "quota_exceeded": ("오늘 사용량을 다 썼다냥 (내일 다시 해 보겠다옹)", False),
    "rate_limit_exceeded": ("요청이 너무 많다냥 (잠시 뒤 다시 해 보겠다옹)", True),
    "too_many_requests": ("요청이 너무 많다냥 (잠시 뒤 다시 해 보겠다옹)", True),
    "service_unavailable": ("구글 서버가 바쁘다냥 (잠시 뒤 다시 해 보겠다옹)", True),
    "deadline_exceeded": ("구글 서버가 너무 오래 걸린다냥 (잠시 뒤 다시 해 보겠다옹)", True),
    "api_error": ("구글 서버에 문제가 생겼다냥 (잠시 뒤 다시 해 보겠다옹)", True),
}
_BLOCKED = ("safety", "recitation", "language", "prohibited_content", "spii", "blocklist")


def _scrub(text: str, key: str) -> str:
    return text.replace(key, "***") if key else text


def _http_error(status, body: bytes, key: str) -> GeminiError:
    code, msg = "", ""
    try:
        e = json.loads(body.decode("utf-8", "replace")).get("error", {})
        code, msg = str(e.get("code", "")), str(e.get("message", ""))
    except Exception:
        pass
    if not code:                                                # 문서: 목록에 없으면 HTTP 상태의 snake_case
        code = {400: "invalid_request", 401: "authentication", 403: "permission_denied", 404: "not_found", 429: "too_many_requests",
                500: "api_error", 503: "service_unavailable", 504: "deadline_exceeded"}.get(status, "")
    if code in _BLOCKED:
        return GeminiError("안전 정책 때문에 답을 못 만들었다냥 (프롬프트를 바꿔 보라옹)")
    if status == 429 and "quota" in msg.lower():             # '한도를 넘었다'는 429 는 기다려도 소용없다 (예: 무료 등급에서 막힌 기능을 쓴 경우)
        return GeminiError("이 키의 사용 한도에 걸렸다냥 (무료 등급에서 막힌 기능이거나 사용량을 넘긴 것 같다옹. AI Studio에서 확인해 달라냥)")
    if code in _MESSAGES:
        m, retry = _MESSAGES[code]
        return GeminiError(m, retry)
    if status >= 500:
        return GeminiError("구글 서버에 문제가 생겼다냥 (잠시 뒤 다시 해 보겠다옹)", True)
    detail = _scrub(msg, key)[:120]
    return GeminiError("Gemini가 요청을 거절했다냥 (%d%s)" % (status, ": " + detail if detail else ""))


def _post(url: str, body: dict, key: str, timeout: float):
    """(상태 코드, 응답 바이트)를 돌려준다. 네트워크 오류는 GeminiError."""
    import socket
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key, "User-Agent": "DesktopCat/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(8 * 1024 * 1024)
    except urllib.error.HTTPError as e:
        return e.code, e.read(1024 * 1024)
    except (socket.timeout, TimeoutError):
        raise GeminiError("Gemini 서버가 대답이 없다냥 (시간 초과)", True) from None
    except urllib.error.URLError as e:
        if isinstance(e.reason, (socket.timeout, TimeoutError)):
            raise GeminiError("Gemini 서버가 대답이 없다냥 (시간 초과)", True) from None
        raise GeminiError("Gemini에 연결을 못 했다냥 (인터넷을 확인해 달라옹)", True) from None
    except Exception:
        raise GeminiError("Gemini에 연결을 못 했다냥 (인터넷을 확인해 달라옹)", True) from None


# ---------------------------------------------------------------- 응답 해석
def parse_interaction(data: dict) -> dict:
    """Interactions 응답 → {"text": 본문, "sources": [{"title", "url"}]}"""
    texts, sources, seen = [], [], set()
    for step in data.get("steps") or []:
        if step.get("type") != "model_output":
            continue
        for c in step.get("content") or []:
            if c.get("type") != "text":
                continue
            texts.append(c.get("text", ""))
            for a in c.get("annotations") or []:
                if a.get("type") == "url_citation" and a.get("url") and a["url"] not in seen:
                    seen.add(a["url"])
                    sources.append({"title": a.get("title") or a["url"], "url": a["url"]})
    return {"text": "".join(texts).strip(), "sources": sources}


def parse_generate_content(data: dict) -> dict:
    """generateContent 응답 → 같은 모양."""
    texts, sources, seen = [], [], set()
    cands = data.get("candidates") or []
    if cands:
        for part in (cands[0].get("content") or {}).get("parts") or []:
            if "text" in part:
                texts.append(part["text"])
        for ch in (cands[0].get("groundingMetadata") or {}).get("groundingChunks") or []:
            w = ch.get("web") or {}
            if w.get("uri") and w["uri"] not in seen:
                seen.add(w["uri"])
                sources.append({"title": w.get("title") or w["uri"], "url": w["uri"]})
    return {"text": "".join(texts).strip(), "sources": sources}


# ---------------------------------------------------------------- 호출
def generate(key: str, model: str, prompt: str, system: str = SYSTEM, search: bool = True, timeout: float = 90.0,
             retries: int = 2) -> dict:
    """프롬프트를 보내고 {"text", "sources"} 를 돌려준다. 실패하면 GeminiError.
    429/503/5xx 같은 일시적 오류는 쉬었다가(3초, 8초) 최대 retries 번 다시 시도한다."""
    key, model = (key or "").strip(), (model or "").strip() or DEFAULT_MODEL
    if not key:
        raise GeminiError("Gemini 키가 없다냥 (설정 → 소식에서 입력해 달라옹)")
    last = None
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(RETRY_DELAYS[attempt - 1])
        try:
            return _generate_once(key, model, prompt, system, search, timeout)
        except GeminiError as e:
            last = e
            if not e.retry:
                break
    raise last


def _generate_once(key, model, prompt, system, search, timeout) -> dict:
    full = {"model": model, "input": prompt, "system_instruction": system, "store": False}
    if search:
        full["tools"] = [{"type": "google_search"}]
    minimal = {"model": model, "input": system + "\n\n" + prompt}
    if search:
        minimal["tools"] = [{"type": "google_search"}]
    # 1) Interactions API: 먼저 모든 옵션을 넣어서, 모르는 매개변수라는 오류면 가장 단순한 본문으로 한 번 더
    status, body = _post(BASE + "/interactions", full, key, timeout)
    if status == 400 and b"parameter_unknown" in body:
        status, body = _post(BASE + "/interactions", minimal, key, timeout)
    if status in (404, 405) and b"model_not_found" not in body:
        # 2) 되돌림: generateContent
        gc = {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"parts": [{"text": prompt}]}]}
        if search:
            gc["tools"] = [{"google_search": {}}]
        status, body = _post("%s/models/%s:generateContent" % (BASE, model), gc, key, timeout)
        parser = parse_generate_content
    else:
        parser = parse_interaction
    if status != 200:
        raise _http_error(status, body, key)
    try:
        out = parser(json.loads(body.decode("utf-8", "replace")))
    except ValueError:
        raise GeminiError("Gemini 대답을 읽지 못했다냥") from None
    if not out["text"]:
        raise GeminiError("Gemini가 빈 답을 보냈다냥 (프롬프트를 바꿔 보라옹)", True)
    return out
