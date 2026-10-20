"""구글 캘린더 '비공개 주소(iCal 형식)'에서 오늘 일정을 가져온다.

 · 반복 일정(매주 회의 등)과 시간대는 icalendar + recurring-ical-events 라이브러리가 처리한다.
 · 네트워크 호출이라 고양이의 화면 갱신 스레드에서 부르면 안 된다 (scheduler.py 가 작업 스레드에서 부른다).
 · 이 주소는 캘린더 전체를 읽을 수 있는 비밀 값이다: 로그에 남기지 않고, 오류 메시지에도 주소를 넣지 않는다.
"""
import datetime as dt

MAX_BYTES = 8 * 1024 * 1024          # 이보다 큰 캘린더는 받지 않는다 (잘못된 주소·악의적인 응답 방지)


class CalendarError(Exception):
    """사용자에게 그대로 보여 줄 수 있는 한국어 메시지를 담는다 (주소는 넣지 않는다). retry=True 면 잠시 뒤 다시 해 볼 만한 오류(인터넷·서버 문제)."""

    def __init__(self, message, retry=False):
        super().__init__(message)
        self.retry = retry


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if url.lower().startswith("webcal://"):
        url = "https://" + url[9:]
    if not url.lower().startswith(("https://", "http://")):
        raise CalendarError("캘린더 주소가 이상하다냥 (https:// 로 시작해야 한다옹)")
    return url


def fetch_text(url: str, timeout: float = 10.0) -> str:
    """주소에서 iCal 본문을 가져온다. 표준 라이브러리(urllib)만 쓴다: requests 는 불러오기만 해도 메모리 약 21MB·1.2초가 들어서 뺐다."""
    import socket
    import urllib.error
    import urllib.request
    url = normalize_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": "DesktopCat/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404, 410):
            raise CalendarError("캘린더 주소가 틀렸거나 바뀌었다냥 (비공개 주소를 다시 복사해 달라옹)") from None
        raise CalendarError("캘린더를 못 가져왔다냥 (응답 %d)" % e.code, e.code >= 500 or e.code == 429) from None
    except (socket.timeout, TimeoutError):
        raise CalendarError("캘린더 서버가 응답하지 않아요 (시간 초과)", True) from None
    except urllib.error.URLError as e:
        if isinstance(e.reason, (socket.timeout, TimeoutError)):
            raise CalendarError("캘린더 서버가 응답하지 않아요 (시간 초과)", True) from None
        raise CalendarError("캘린더에 연결을 못 했다냥 (인터넷을 확인해 달라옹)", True) from None
    except Exception:
        raise CalendarError("캘린더에 연결을 못 했다냥 (인터넷을 확인해 달라옹)", True) from None
    if len(data) > MAX_BYTES:
        raise CalendarError("캘린더가 너무 커요")
    return data.decode("utf-8", errors="replace")


def _local(value):
    """icalendar 의 날짜·시간 값을 (종일 여부, 이 컴퓨터 시간대의 datetime 또는 date) 로."""
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            return False, value                                  # 시간대 없는 일정: 이 컴퓨터 시간으로 본다
        return False, value.astimezone().replace(tzinfo=None)
    return True, value                                           # date: 종일 일정


def events_on(text: str, day: dt.date) -> list:
    """iCal 본문에서 day 날짜의 일정을 [{'all_day': bool, 'start': datetime, 'summary': str}] 로 (종일 먼저, 시각 순)."""
    import icalendar
    import recurring_ical_events
    try:
        cal = icalendar.Calendar.from_ical(text)
    except Exception:
        raise CalendarError("캘린더 내용을 못 읽겠다냥 (iCal 형식이 아니다옹)") from None
    out = []
    for ev in recurring_ical_events.of(cal).at((day.year, day.month, day.day)):
        if str(ev.get("STATUS", "")).upper() == "CANCELLED":
            continue
        start = ev.get("DTSTART")
        if start is None:
            continue
        all_day, s = _local(start.dt)
        if all_day:
            start_dt = dt.datetime.combine(s, dt.time.min)
        else:
            start_dt = s
        summary = str(ev.get("SUMMARY", "")).strip() or "(제목 없음)"
        out.append({"all_day": all_day, "start": start_dt, "summary": summary})
    out.sort(key=lambda e: (not e["all_day"], e["start"], e["summary"]))
    return out


def today_events(url: str, now: dt.datetime | None = None) -> list:
    now = now or dt.datetime.now()
    return events_on(fetch_text(url), now.date())


def format_lines(events: list, limit: int = 5) -> list[str]:
    """풍선에 보여 줄 줄들. 일정이 없으면 한 줄, limit 을 넘으면 '외 N개'."""
    if not events:
        return ["오늘 일정은 없다냥~ 🐾"]
    lines = ["📅 오늘 일정 %d개" % len(events)]
    for e in events[:limit]:
        lines.append(("종일  " if e["all_day"] else e["start"].strftime("%H:%M  ")) + e["summary"])
    if len(events) > limit:
        lines.append("… 외 %d개" % (len(events) - limit))
    return lines



# ---------------------------------------------------------------- 매시 정각: 앞으로 N시간 일정
def events_between(text: str, start: dt.datetime, end: dt.datetime) -> list:
    """[start, end) 와 겹치는 '시각이 있는' 일정을 시각순으로 (종일 일정은 제외). 진행 중인 일정(start 전에 시작)도 포함한다.
    [{'start': datetime, 'end': datetime, 'summary': str, 'ongoing': bool}]"""
    import icalendar
    import recurring_ical_events
    try:
        cal = icalendar.Calendar.from_ical(text)
    except Exception:
        raise CalendarError("캘린더 내용을 못 읽겠다냥 (iCal 형식이 아니다옹)") from None
    local = dt.datetime.now().astimezone().tzinfo
    s_aw = start.replace(tzinfo=local) if start.tzinfo is None else start
    e_aw = end.replace(tzinfo=local) if end.tzinfo is None else end
    out = []
    for ev in recurring_ical_events.of(cal).between(s_aw, e_aw):
        if str(ev.get("STATUS", "")).upper() == "CANCELLED":
            continue
        ds = ev.get("DTSTART")
        if ds is None:
            continue
        all_day, s = _local(ds.dt)
        if all_day:
            continue
        de = ev.get("DTEND")
        if de is not None:
            _, e = _local(de.dt)
            if not isinstance(e, dt.datetime):
                e = s
        else:
            dur = ev.get("DURATION")
            e = s + dur.dt if dur is not None else s
        if e < s:
            e = s
        s_naive = start.replace(tzinfo=None)
        e_naive = end.replace(tzinfo=None)
        if s >= e_naive or (e <= s_naive and not (e == s == s_naive)):      # 창과 안 겹침 (시작 시각 딱 맞는 0분 일정은 포함)
            continue
        out.append({"start": s, "end": e, "summary": str(ev.get("SUMMARY", "")).strip() or "(제목 없음)", "ongoing": s < s_naive})
    out.sort(key=lambda x: (x["start"], x["summary"]))
    return out


def upcoming_events(url: str, hours: int = 2, now: dt.datetime | None = None) -> list:
    now = (now or dt.datetime.now()).replace(second=0, microsecond=0)
    return events_between(fetch_text(url), now, now + dt.timedelta(hours=hours))


def format_upcoming(events: list, hours: int = 2, limit: int = 5) -> list[str]:
    """풍선 줄들. 일정이 없으면 빈 목록(매시 알림은 일정이 없으면 조용히 넘어간다)."""
    if not events:
        return []
    lines = ["📅 앞으로 %d시간 일정 %d개" % (hours, len(events))]
    for e in events[:limit]:
        span = "%s~%s" % (e["start"].strftime("%H:%M"), e["end"].strftime("%H:%M")) if e["end"] > e["start"] else e["start"].strftime("%H:%M")
        lines.append("%s  %s%s" % (span, e["summary"], "  (진행 중)" if e["ongoing"] else ""))
    if len(events) > limit:
        lines.append("… 외 %d개" % (len(events) - limit))
    return lines
