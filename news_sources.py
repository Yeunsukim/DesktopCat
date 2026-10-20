"""소식 자료 모으기: 날씨·뉴스·시세를 무료 공개 주소에서 직접 가져온다 (nethelper 보조 프로세스 안에서 실행).

Gemini 의 '구글 검색' 도구는 무료 등급에서 막혀 있어서(검색을 켠 호출만 한도 초과로 거절됨), 고양이가 자료를 직접 모으고
Gemini 에게는 '정리·요약'만 시킨다. 각 자료는 따로 실패해도 되고(나머지만 보여 줌), 키가 필요 없다.
 · 날씨: Open-Meteo (위치는 기본으로 이 컴퓨터의 IP 주소에서 대략 찾고, 설정에서 주요 도시를 직접 고를 수도 있음 → 오늘 예보)
 · 뉴스: Google 뉴스 RSS (한국 주요 뉴스)
 · 시세: Yahoo Finance 차트 주소 (지수·환율, 마지막 두 거래일 종가로 등락 계산)
"""
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = {"User-Agent": "Mozilla/5.0 DesktopCat/1.0"}
AUTO = "자동"                       # 지역 설정이 이 값이면 이 컴퓨터의 IP 주소로 위치를 찾는다
DEFAULT_CITY = AUTO
DEFAULT_QUOTES = "코스피=^KS11\n코스닥=^KQ11\n나스닥=^IXIC\n원/달러=KRW=X"
NEWS_URL = "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko"
NEWS_COUNT = 12

WMO = {0: "맑음", 1: "대체로 맑음", 2: "구름 조금", 3: "흐림", 45: "안개", 48: "안개", 51: "이슬비", 53: "이슬비", 55: "이슬비",
       56: "어는 비", 57: "어는 비", 61: "비", 63: "비", 65: "강한 비", 66: "어는 비", 67: "어는 비", 71: "눈", 73: "눈", 75: "많은 눈",
       77: "싸락눈", 80: "소나기", 81: "소나기", 82: "강한 소나기", 85: "소낙눈", 86: "소낙눈", 95: "천둥번개", 96: "우박 동반 천둥번개",
       99: "우박 동반 천둥번개"}


def _get(url: str, timeout: float = 12.0, limit: int = 1_000_000) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read(limit)


def parse_quotes(text: str):
    """'이름=심볼' 줄들 → [(이름, 심볼)]. 이상한 줄은 버린다 (심볼은 영문·숫자·^=.- 만)."""
    out = []
    for line in (text or "").splitlines():
        if "=" not in line:
            continue
        name, sym = line.split("=", 1)
        name, sym = name.strip(), sym.strip()
        if name and re.fullmatch(r"[A-Za-z0-9^=.\-]{1,20}", sym):
            out.append((name[:20], sym))
    return out[:12]


# ---------------------------------------------------------------- 날씨
CITIES = {"서울": (37.5665, 126.9780), "부산": (35.1796, 129.0756), "대구": (35.8714, 128.6014), "인천": (37.4563, 126.7052),
          "광주": (35.1595, 126.8526), "대전": (36.3504, 127.3845), "울산": (35.5384, 129.3114), "세종": (36.4800, 127.2890),
          "수원": (37.2636, 127.0286), "성남": (37.4200, 127.1267), "고양": (37.6584, 126.8320), "용인": (37.2411, 127.1776),
          "창원": (35.2280, 128.6811), "청주": (36.6424, 127.4890), "전주": (35.8242, 127.1480), "천안": (36.8151, 127.1139),
          "춘천": (37.8813, 127.7298), "강릉": (37.7519, 128.8761), "포항": (36.0190, 129.3435), "제주": (33.4996, 126.5312),
          "안양": (37.3943, 126.9568), "부천": (37.5034, 126.7660), "안산": (37.3219, 126.8309), "화성": (37.1996, 126.8312),
          "평택": (36.9921, 127.1129), "의정부": (37.7381, 127.0337), "시흥": (37.3800, 126.8030), "파주": (37.7599, 126.7750),
          "김포": (37.6153, 126.7156), "광명": (37.4786, 126.8644), "구리": (37.5943, 127.1296), "남양주": (37.6360, 127.2165),
          "하남": (37.5393, 127.2148), "오산": (37.1498, 127.0772), "이천": (37.2720, 127.4350), "원주": (37.3422, 127.9202),
          "속초": (38.2070, 128.5918), "동해": (37.5247, 129.1143), "충주": (36.9910, 127.9259), "제천": (37.1326, 128.1909),
          "아산": (36.7898, 127.0018), "서산": (36.7845, 126.4503), "당진": (36.8897, 126.6459), "군산": (35.9676, 126.7369),
          "익산": (35.9483, 126.9577), "목포": (34.8118, 126.3922), "여수": (34.7604, 127.6622), "순천": (34.9507, 127.4872),
          "광양": (34.9407, 127.6959), "나주": (35.0160, 126.7108), "구미": (36.1195, 128.3446), "경주": (35.8562, 129.2247),
          "안동": (36.5684, 128.7294), "김해": (35.2285, 128.8894), "양산": (35.3350, 129.0373), "진주": (35.1800, 128.1076),
          "거제": (34.8806, 128.6211), "통영": (34.8544, 128.4331), "서귀포": (33.2541, 126.5600)}
# 한글 도시 이름은 Open-Meteo 의 이름 검색이 잘 못 찾아서(부산이 엉뚱한 곳으로 나옴) 주요 도시는 좌표를 직접 갖고 있는다.


def _nearest_korean(lat: float, lon: float):
    """가까운(30km 안) 주요 도시가 있으면 그 한글 이름, 없으면 None."""
    import math
    best, bd = None, 1e9
    for name, (la, lo) in CITIES.items():
        d = math.hypot((lat - la) * 111.0, (lon - lo) * 111.0 * math.cos(math.radians(lat)))
        if d < bd:
            best, bd = name, d
    return best if bd <= 30 else None


def locate():
    """이 컴퓨터의 인터넷 주소(IP)로 대략적인 위치를 찾는다: (이름, (위도, 경도)).
    무료 위치 조회 서비스 3곳을 차례로 시도한다. 집 주소가 아니라 통신사가 등록한 '대략 이 동네' 수준이다."""
    for url in ("https://ipwho.is/", "https://get.geojs.io/v1/ip/geo.json", "https://ipapi.co/json/"):
        try:
            j = json.loads(_get(url, 8.0, 20000))
            lat, lon = float(j["latitude"]), float(j["longitude"])
            return _nearest_korean(lat, lon) or j.get("city") or j.get("region") or "현재 위치", (lat, lon)
        except Exception:
            continue
    raise ValueError("위치를 찾지 못함")


def _place(city: str):
    city = (city or AUTO).strip()
    if city in (AUTO, "auto", ""):
        try:
            return locate()
        except Exception:
            return "서울(위치를 못 찾아 기본값)", CITIES["서울"]
    key = re.sub(r"(특별자치시|특별자치도|특별시|광역시|시)$", "", city) or "서울"
    if key in CITIES:
        return key, CITIES[key]
    g = json.loads(_get("https://geocoding-api.open-meteo.com/v1/search?count=1&language=ko&name=" + urllib.parse.quote(city)))
    r = (g.get("results") or [None])[0]
    if not r:
        raise ValueError("도시를 찾지 못함")
    return r.get("name", city), (r["latitude"], r["longitude"])


def weather(city: str) -> str:
    return weather_info(city)[1]


def weather_info(city: str):
    """(지역 이름, 날씨 한 줄)"""
    name, (lat, lon) = _place(city)
    q = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&timezone=auto&forecast_days=1"
         "&current=temperature_2m,apparent_temperature,weather_code"
         "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code") % (lat, lon)
    w = json.loads(_get(q))
    c, d = w["current"], w["daily"]
    code = d["weather_code"][0]
    return name, ("%s 오늘 날씨: %s, 현재 %.0f도(체감 %.0f도), 최저 %.0f도·최고 %.0f도, 강수확률 %s%%"
            % (name, WMO.get(code, "날씨 코드 %s" % code), c["temperature_2m"], c["apparent_temperature"],
               d["temperature_2m_min"][0], d["temperature_2m_max"][0], d["precipitation_probability_max"][0]))


# ---------------------------------------------------------------- 뉴스
def news():
    """[{"title", "url"}] (Google 뉴스 주요 기사, 제목 끝에 ' - 언론사')"""
    root = ET.fromstring(_get(NEWS_URL))
    items = []
    for it in root.iter("item"):
        t, link = (it.findtext("title") or "").strip(), (it.findtext("link") or "").strip()
        if t and link.startswith("http"):
            items.append({"title": t, "url": link})
        if len(items) >= NEWS_COUNT:
            break
    if not items:
        raise ValueError("뉴스가 비어 있음")
    return items


# ---------------------------------------------------------------- 시세
def quote(name: str, symbol: str) -> str:
    j = json.loads(_get("https://query1.finance.yahoo.com/v8/finance/chart/%s?range=10d&interval=1d" % urllib.parse.quote(symbol, safe="")))
    res = j["chart"]["result"][0]
    closes = [x for x in res["indicators"]["quote"][0]["close"] if x is not None]
    if len(closes) < 2:
        raise ValueError("시세가 모자람")
    last, prev = closes[-1], closes[-2]
    pct = (last - prev) / prev * 100
    return "%s: %s (전일 대비 %s%.2f%%)" % (name, format(last, ",.2f"), "+" if pct >= 0 else "", pct)


def add_place(text: str, place: str) -> str:
    """날씨 소제목(# 줄 중 '날씨'가 들어간 첫 줄)에 '(지역)'을 붙인다. 이미 괄호가 있거나 지역을 모르면 그대로 둔다.
    Gemini 가 알아서 넣어 주길 기대하지 않고 코드가 확실하게 넣는다."""
    if not place:
        return text
    out, done = [], False
    for line in text.splitlines():
        if not done and line.lstrip().startswith("#") and "날씨" in line:
            done = True
            if "(" not in line:
                line = "%s (%s)" % (line.rstrip(), place)
        out.append(line)
    return "\n".join(out)


# ---------------------------------------------------------------- 모아서 한 덩어리로
def collect(city: str, quotes_text: str) -> dict:
    """{"digest": Gemini 에게 줄 자료 글, "sources": [{"title","url"}], "ok": 성공한 자료 수}. 실패한 자료는 '못 가져옴'으로 적는다."""
    parts, sources, ok, place = [], [], 0, ""
    try:
        place, text = weather_info(city or DEFAULT_CITY)
        parts.append("[날씨]\n" + text)
        ok += 1
    except Exception:
        parts.append("[날씨]\n(가져오지 못함)")
    try:
        items = news()
        parts.append("[뉴스 헤드라인]\n" + "\n".join("%d. %s" % (i + 1, x["title"]) for i, x in enumerate(items)))
        sources = items[:10]
        ok += 1
    except Exception:
        parts.append("[뉴스 헤드라인]\n(가져오지 못함)")
    lines = []
    for name, sym in parse_quotes(quotes_text):
        try:
            lines.append(quote(name, sym))
            ok += 1
        except Exception:
            lines.append("%s: (가져오지 못함)" % name)
    if lines:
        parts.append("[시세]\n" + "\n".join(lines))
    return {"digest": "\n\n".join(parts), "sources": sources, "ok": ok, "place": place}
