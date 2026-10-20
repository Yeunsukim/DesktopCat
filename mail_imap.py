"""Gmail 새 메일 확인: '누구에게서 왔는지'만 읽는다 (nethelper 보조 프로세스 안에서 실행된다).

 · 방식: 구글 계정의 '앱 비밀번호'로 IMAP(imap.gmail.com:993, 암호화)에 로그인한다. 구글 로그인 창이나 별도 개발자 등록이 필요 없다.
   (구글 계정에서 2단계 인증을 켠 뒤 '앱 비밀번호'를 만들어야 한다.)
 · 읽는 것: 안 읽은 메일 목록과 각 메일의 '보낸 사람' 머리글(From)뿐이다. 제목·본문은 가져오지 않고, BODY.PEEK 으로 가져와서
   메일을 '읽음'으로 바꾸지도 않으며(읽기 전용으로 연다), 아무것도 지우거나 보내지 않는다.
 · 새 메일 판단: 마지막으로 확인한 메일 번호(UID)보다 큰 '안 읽은' 메일. 처음 확인할 때는 지금 있는 메일을 기준점으로만 삼고
   안 읽은 메일 개수만 알려 준다(쌓여 있던 메일을 한꺼번에 알리지 않게).
 · 시험용: DESKTOPCAT_IMAP_HOST=127.0.0.1:포트 로 이 컴퓨터의 가짜 서버(암호화 없음)에만 연결할 수 있다.
"""
import email.header
import email.utils
import imaplib
import os
import re

HOST, PORT = "imap.gmail.com", 993
_override = os.environ.get("DESKTOPCAT_IMAP_HOST", "")
PLAIN = False
if _override.startswith("127.0.0.1:"):
    HOST, PORT, PLAIN = "127.0.0.1", int(_override.split(":")[1]), True
MAX_NAMES = 8


class MailError(Exception):
    """사용자에게 그대로 보여 줄 한국어 메시지. retry=True 면 잠시 뒤 다시 해 볼 만한 오류."""

    def __init__(self, message, retry=False):
        super().__init__(message)
        self.retry = retry


def _name_of(header_bytes: bytes) -> str:
    """From 머리글 → 보여 줄 이름 (표시 이름이 있으면 그것, 없으면 주소의 앞부분)."""
    raw = header_bytes.decode("utf-8", "replace")
    m = re.search(r"(?im)^From:\s*(.*(?:\r?\n[ \t].*)*)", raw)
    if not m:
        return "알 수 없는 사람"
    value = re.sub(r"\r?\n[ \t]+", " ", m.group(1)).strip()
    try:
        value = str(email.header.make_header(email.header.decode_header(value)))
    except Exception:
        pass
    name, addr = email.utils.parseaddr(value)
    name = name.strip().strip('"')
    return (name or addr.split("@")[0] or "알 수 없는 사람")[:40]


def _login_error(raw: str, password: str) -> "MailError":
    """구글이 로그인을 거절하며 돌려준 말을 알아보기 쉬운 안내로 바꾼다 (비밀번호는 메시지에 넣지 않는다)."""
    low = raw.lower()
    clean = raw.replace(password, "***").strip()[:140]
    if "application-specific password" in low or "app password" in low:
        return MailError("앱 비밀번호가 필요하다냥 (일반 구글 비밀번호가 아니라 ‘앱 비밀번호’ 16자리를 넣어 달라옹)")
    if "web login" in low or "web browser" in low or "webalert" in low:
        return MailError("구글이 보안 확인을 요구한다냥 (브라우저에서 이 계정으로 Gmail에 한 번 로그인해서 확인한 뒤 다시 해 달라옹)")
    if "imap" in low and ("disabled" in low or "not enabled" in low):
        return MailError("Gmail에서 IMAP 사용이 꺼져 있다냥 (Gmail 설정 → 전달 및 POP/IMAP에서 켜 달라옹)")
    if "authenticationfailed" in low or "invalid credentials" in low or "username and password not accepted" in low:
        return MailError("메일 로그인에 실패했다냥 (주소와 ‘앱 비밀번호’ 16자리를 확인해 달라옹. 일반 비밀번호는 안 된다냥)")
    return MailError("Gmail이 로그인을 거절했다냥 (서버 응답: %s)" % clean)


def _uids(data) -> list:
    out = []
    for chunk in data or []:
        if isinstance(chunk, bytes):
            out += [int(x) for x in chunk.split() if x.isdigit()]
    return sorted(set(out))


def check(user: str, password: str, last_uid=None, uidvalidity=None, timeout: float = 40.0) -> dict:
    """새 안 읽은 메일을 확인한다.
    돌려주는 값: {"first": 처음 확인인가, "unseen": 안 읽은 메일 수, "new": [보낸 사람 이름…], "new_count": 새 메일 수,
                 "last_uid": 새 기준 UID, "uidvalidity": 사서함 식별 번호}"""
    user, password = (user or "").strip(), re.sub(r"\s+", "", password or "")           # 앱 비밀번호는 'abcd efgh ijkl mnop' 처럼 공백이 섞여 보인다
    if not user or not password:
        raise MailError("메일 주소와 앱 비밀번호를 먼저 넣어 달라냥")
    if not (user.isascii() and password.isascii()):
        raise MailError("메일 주소와 앱 비밀번호는 영문·숫자만 쓸 수 있다냥 (앱 비밀번호를 그대로 붙여 넣어 달라옹)")
    try:
        M = imaplib.IMAP4(HOST, PORT, timeout=timeout) if PLAIN else imaplib.IMAP4_SSL(HOST, PORT, timeout=timeout)
    except (OSError, imaplib.IMAP4.error):
        raise MailError("Gmail에 연결을 못 했다냥 (인터넷을 확인해 달라옹)", True) from None
    try:
        try:
            M.login(user, password)
        except imaplib.IMAP4.error as e:
            raw = e.args[0].decode("utf-8", "replace") if e.args and isinstance(e.args[0], bytes) else str(e)
            raise _login_error(raw, password) from None
        typ, _ = M.select("INBOX", readonly=True)           # 읽기 전용: 메일을 읽음으로 바꾸지 않는다
        if typ != "OK":
            raise MailError("받은편지함을 열지 못했다냥")
        validity = None
        _t, vdata = M.response("UIDVALIDITY")
        if vdata and vdata[0]:
            validity = int(vdata[0])
        first = last_uid is None or validity != uidvalidity
        _t, d_unseen = M.uid("SEARCH", None, "UNSEEN")
        unseen = _uids(d_unseen)
        if first:
            _t, d_top = M.uid("SEARCH", None, "UID", "*")        # 지금 가장 큰 번호를 기준점으로
            top = _uids(d_top)
            return {"first": True, "unseen": len(unseen), "new": [], "new_count": 0,
                    "last_uid": max(top + unseen + [0]), "uidvalidity": validity}
        fresh = [u for u in unseen if u > last_uid]
        names = []
        for u in fresh[-MAX_NAMES:]:
            _t, md = M.uid("FETCH", str(u), "(BODY.PEEK[HEADER.FIELDS (FROM)])")
            hdr = b""
            for part in md or []:
                if isinstance(part, tuple):
                    hdr += part[1]
            names.append(_name_of(hdr))
        return {"first": False, "unseen": len(unseen), "new": names, "new_count": len(fresh),
                "last_uid": max([last_uid] + unseen), "uidvalidity": validity}
    except MailError:
        raise
    except (imaplib.IMAP4.abort, OSError):
        raise MailError("Gmail과 연결이 끊겼다냥 (잠시 뒤 다시 해 보겠다옹)", True) from None
    except imaplib.IMAP4.error:
        raise MailError("메일을 확인하지 못했다냥") from None
    finally:
        try:
            M.logout()
        except Exception:
            pass


def format_lines(res: dict) -> list:
    """풍선에 보여 줄 줄들. 새 메일이 없으면 빈 목록."""
    if res.get("first"):
        return ["📧 안 읽은 메일이 %d통 있다옹" % res["unseen"]] if res.get("unseen") else []
    names = res.get("new") or []
    if not res.get("new_count"):
        return []
    uniq = list(dict.fromkeys(names))
    lines = ["📧 %s에게서 메일 왔다~옹~" % (uniq[0] if len(uniq) == 1 else "%s 외 %d명" % (uniq[0], len(uniq) - 1))]
    if res["new_count"] > 1 or len(uniq) > 1:
        lines.append("새 메일 %d통 (보낸 사람: %s)" % (res["new_count"], ", ".join(uniq[:4]) + (" …" if len(uniq) > 4 else "")))
    return lines
