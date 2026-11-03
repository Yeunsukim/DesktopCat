"""고양이 행동 상태머신, 발판(창/바닥) 판정, 아이콘 차기 물리.

모든 좌표는 논리 픽셀(Qt 좌표)이다. 고양이 위치는 (x = 가로 중심, feet = 발바닥 y).
동작(그림)은 animations.py 의 이름으로 Animator 에게 지시한다.
"""
import math
import random
import time
from enum import Enum, auto

import win32gui

import flow
from animations_runtime import Animator
from windows_info import WindowTracker, frame_rect

G = 1800.0

# 기준 크기(scale=1)에서의 이동 속도 (px/s). 실제 속도는 scale 을 곱한다.
V_WALK, V_TROT, V_RUN, V_SNEAK = 70.0, 150.0, 300.0, 38.0
# 출발·멈춤: 실제 고양이처럼 한두 걸음에 걸쳐 빨라지고 느려진다 (예전에는 첫 순간부터 최고 속도, 멈출 때도 한 번에 섰다).
# 걸음 위상은 이동 거리만큼 넘어가므로 속도를 바꿔도 다리 움직임이 같이 느려져 발이 미끄러지지 않는다.
# 놀아주기(깃털): 마우스 커서가 나비 장난감이 되고 고양이가 쫓아다니며 잡으려 뛴다 (모든 수치는 scale=0.8 기준을 k = scale/0.8 로 환산해서 쓴다)
TEASE_SEC = 10.0                         # 초: 놀아 주는 시간
TEASE_VMAX = 420.0                       # px/s: 쫓아갈 때 최고 속도 (평소 달리기 300 보다 확실히 빠르다)
TEASE_ACC = 3200.0                       # px/s²: 가속·감속 (재빠르게 방향을 바꾼다)
TEASE_G = 3000.0                         # 뛰어오를 때 중력 (평소 낙하 1800 보다 세게: 도약이 짧고 날쌔다)
TEASE_REACH_STAND = 100.0                # px: 서서·앉아서 앞발로 닿는 높이 (발바닥 기준)
TEASE_REACH_AIR = 125.0                  # px: 뛰어올라 몸을 쭉 폈을 때 앞발이 발바닥보다 위로 닿는 높이
TEASE_LEAP_MAX = 430.0                   # px: 한 번에 뛰어오르는 최대 높이 (앞발까지 합치면 발바닥 위 약 555px: 화면 가운데쯤)
TEASE_AIR_T = 0.85                       # 초: 가장 높이 뛸 때 공중에 떠 있는 시간 (높이 뛸수록 중력을 세게 해서 이 시간 안에 오르내린다)
MOTION_SPEED = 1.10                      # 움직임·동작 재생 속도 배율 (10% 빠르게). 나비잡기(깃털 놀이)와 종종걸음은 지금 속도가 좋아서 뺀다 (_motion_speed)
EAT_SEC = 11.0                          # 초: 밥 먹는 시간 (예전 4.5초는 너무 짧았다. 채터링 소리 길이와도 비슷하다)
ACCEL_T, DECEL_T = 0.35, 0.30            # 초: 최고 속도까지 / 멈출 때까지 걸리는 시간
STOP_MAX = 0.6                           # 초: 걷기가 끝나고 멈추는 데 쓰는 최대 시간


# 말풍선에 나오는 모든 문구 (시작할 때 한꺼번에 글자 폭을 재 두어서, 처음 나올 때 멈칫하지 않게 한다)
SAYINGS = (
    "냐옹~",
    "배고프당...옹~ 🐟",
    "밥 줘랑..옹~ 🐟",
    "냐아아…",
    "♪ 랄라냐옹~",
    "냐옹~ ❤️",
    "😸 기분 좋다냐옹~",
    "… 냐앙…",
    "심심하당..옹~ 😿",
    "후아암~ 누구냥.. 😺",
    "😋 맛있당..옹~",
    "🐾 에잇냐옹!",
    "🧶 털실이다냐옹~!",
    "🦋 나비다냐옹!",
    "😸 재밌냐옹~",
    "배부르당..옹~ 😾",
    "🐟 냠냠냥~",
    "…😾 깨웠냐옹…",
    "❤️ 좋다냐옹~",
    "냥?! 뭐냐옹?!",
    "우다다다냐옹!",
    "골골~ 💤",
    "냥이펀치 냥이펀치 꾹꾹이~ 🐾",
    "✨ 정리 끝이냐옹~",               # cat.py 의 '아이콘 원래대로' 메뉴
    "정리할 게 없다냐옹~",
)


class S(Enum):
    IDLE = auto()
    SIT = auto()
    SITTILT = auto()
    LOAF = auto()
    SLEEP = auto()
    WALK = auto()
    RUN = auto()
    SNEAK = auto()
    JUMP = auto()
    FALL = auto()
    KICK_WALK = auto()
    KICK_LEAP = auto()
    KICK_HIT = auto()
    EAT = auto()
    STROKE = auto()
    PLAY = auto()
    GROOM = auto()
    YAWN = auto()
    STRETCH = auto()
    SCRATCH = auto()
    GROOMLEG = auto()
    SCRATCHNECK = auto()
    GROOMFACE = auto()
    KNEAD = auto()
    TAILPLAY = auto()
    HUNT = auto()                    # 쥐 잡기 (경비 경보 연출)
    TEASE = auto()                   # 놀아주기(깃털): 커서 나비를 쫓아다니며 잡으려 뛴다
    HELD = auto()


REST_STATES = {S.IDLE, S.SIT, S.SITTILT, S.LOAF, S.SLEEP, S.GROOM, S.GROOMLEG, S.SCRATCHNECK, S.GROOMFACE, S.YAWN, S.STRETCH, S.SCRATCH, S.KNEAD, S.TAILPLAY,
               S.EAT, S.STROKE}
GROUND_MOVE = {S.WALK, S.RUN, S.SNEAK, S.KICK_WALK, S.PLAY, S.HUNT, S.TEASE}
STATE_ANIM = {
    S.IDLE: "stand", S.SIT: "sit", S.SITTILT: "sit_tilt", S.LOAF: "loaf", S.GROOM: "groom", S.YAWN: "yawn", S.STRETCH: "stretch",
    S.SCRATCH: "scratch", S.GROOMLEG: "groom_leg", S.SCRATCHNECK: "scratch_neck", S.GROOMFACE: "groom_face", S.KNEAD: "knead", S.TAILPLAY: "tail_play", S.EAT: "eat", S.STROKE: "stroke",
    S.FALL: "fall", S.HELD: "hold", S.KICK_HIT: "swat", S.RUN: "run", S.SNEAK: "sneak",
}
SLEEP_ANIMS = ("sleep_curl", "sleep_side", "sleep_nap", "sleep_doze")


# ---------------------------------------------------------------------------
class World:
    """모니터별 작업 영역(바닥)과 창 윗변(발판) 정보.

    모니터가 여러 개면 고양이는 모니터 사이를 걸어서 오갈 수 있다. 바닥 높이가 같고 이어져 있는 모니터들은
    하나의 '띠(strip)'로 묶여 한 바닥처럼 걷는다. 높이가 다른 모니터는 창 위로 뛰어오르거나 떨어져서 건너간다."""

    def __init__(self, areas, tracker: WindowTracker, dpr: float, cat_h: float):
        self.tracker = tracker
        self.dpr = dpr
        self.min_top = cat_h * 0.9          # 이보다 위에 있는 창 윗변은 올라가도 화면 밖이므로 제외
        self.wins = []
        self.set_areas(areas)

    def set_areas(self, areas):
        """areas: (left, top, right, bottom) 작업 영역 목록 (맨 앞이 주 모니터). 사각형 하나만 줘도 된다."""
        if areas and isinstance(areas[0], (int, float)):
            areas = [areas]
        self.areas = [tuple(float(v) for v in a) for a in areas]
        self.bbox = (min(a[0] for a in self.areas), min(a[1] for a in self.areas),
                     max(a[2] for a in self.areas), max(a[3] for a in self.areas))
        first = self.areas[0]
        self.start_x = (first[0] + first[2]) / 2
        self.cx = self.start_x              # 고양이의 현재 x: 바닥·좌우 한계는 고양이가 있는 모니터 기준

    def strip_at(self, x):
        """x 가 있는 모니터와, 바닥 높이가 같고 이어진 모니터들을 묶은 (left, right, bottom, [areas])."""
        def dist(a):
            return 0.0 if a[0] <= x <= a[2] else min(abs(x - a[0]), abs(x - a[2]))
        cur = min(self.areas, key=dist)
        strip, left, right, bottom = [cur], cur[0], cur[2], cur[3]
        grew = True
        while grew:
            grew = False
            for a in self.areas:
                if a not in strip and abs(a[3] - bottom) <= 6 and a[0] <= right + 4 and a[2] >= left - 4:
                    strip.append(a)
                    left, right = min(left, a[0]), max(right, a[2])
                    grew = True
        return left, right, bottom, strip

    @property
    def left(self):
        return self.strip_at(self.cx)[0]

    @property
    def right(self):
        return self.strip_at(self.cx)[1]

    @property
    def floor(self):
        return self.strip_at(self.cx)[2]

    def neighbors(self, x):
        """지금 바닥(띠)의 왼쪽/오른쪽 끝에 맞닿아 있지만 바닥 높이가 다른 모니터들: [(방향, 영역)]. 방향 +1=오른쪽, -1=왼쪽."""
        left, right, bottom, strip = self.strip_at(x)
        out = []
        for a in self.areas:
            if a in strip:
                continue
            if abs(a[0] - right) <= 4:
                out.append((1, a))
            elif abs(a[2] - left) <= 4:
                out.append((-1, a))
        return out

    def other_areas(self, x):
        """지금 걷는 바닥 위에 있는 다른 모니터들 (걸어서 갈 수 있는 곳)."""
        strip = self.strip_at(x)[3]
        cur = min(strip, key=lambda a: 0.0 if a[0] <= x <= a[2] else min(abs(x - a[0]), abs(x - a[2])))
        return [a for a in strip if a is not cur]

    def refresh(self):
        self.wins = self.tracker.refresh(0.4)

    def rect_of(self, hwnd):
        """특정 창의 최신 사각형(창을 끄는 중에도 따라가기 위해 매 프레임 직접 조회)."""
        try:
            if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
                return None
            l, t, r, b = frame_rect(hwnd)
        except Exception:
            return None
        d = self.dpr
        return l / d, t / d, r / d, b / d

    def _occluded(self, i, x):
        top = self.wins[i].top
        for w in self.wins[:i]:
            if w.left <= x <= w.right and w.top <= top - 3 <= w.bottom:
                return True
        return False

    def surfaces_below(self, x, feet, tol=1.5):
        """feet 이하(아래)에 있으면서 x가 올라설 수 있는 발판 [(top, hwnd|None)] 위→아래 정렬."""
        res = []
        for i, w in enumerate(self.wins):
            if w.top < self.min_top or w.top < feet - tol:
                continue
            if w.left + 8 <= x <= w.right - 8 and not self._occluded(i, x):
                res.append((w.top, w.hwnd))
        res.append((self.floor, None))
        res.sort(key=lambda s: s[0])
        return res

    def jump_targets(self, x, feet, max_rise=620, max_dx=380):
        """지금 위치에서 뛰어오를 수 있는 더 높은 창들: [(landing_x, top, hwnd)]."""
        out = []
        for i, w in enumerate(self.wins):
            rise = feet - w.top
            if rise < 40 or rise > max_rise or w.top < self.min_top:
                continue
            lx = min(max(x, w.left + 40), w.right - 40)
            if w.right - w.left < 100 or abs(lx - x) > max_dx or self._occluded(i, lx):
                continue
            out.append((lx, w.top, w.hwnd))
        return out


# ---------------------------------------------------------------------------
class IconField:
    """바탕화면 아이콘 목록과, 차여서 미끄러지는 아이콘의 물리."""

    FRICTION = 2.2

    def __init__(self, icons, dpr: float, bounds, origin=(0.0, 0.0)):
        self.icons = icons
        self.dpr = dpr
        self.origin = origin                # 바탕화면 목록 좌표의 (0,0) 이 놓인 화면 위치 = 모든 모니터를 합친 가상 화면의 왼쪽 위
        self.enabled = bool(icons and icons.attached and icons.is_visible() and not icons.is_autoarrange())
        self.bounds = bounds
        self.cell = (76.0, 93.0)
        self.items = []
        self.moving: dict[int, dict] = {}
        if self.enabled:
            cx, cy = icons.spacing()
            self.cell = (cx / dpr, cy / dpr)

    def scan(self):
        if not self.enabled or not self.icons.revalidate():      # 탐색기가 다시 시작됐으면 연결을 되살린다
            return []
        d = self.dpr
        self.items = []
        for i in range(self.icons.count()):
            px, py = self.icons.position(i)
            self.items.append({"index": i, "x": px / d + self.origin[0], "y": py / d + self.origin[1]})
        return self.items

    def candidates(self):
        l, t, r, b = self.bounds
        cw, ch = self.cell
        return [it for it in self.items
                if it["index"] not in self.moving and l <= it["x"] <= r - cw and t <= it["y"] <= b - ch]

    def launch(self, item, vx, vy):
        note = getattr(self.icons, "note_kick", None)
        if note:
            try:
                note(item["index"])                   # 차기 전에 원래 위치를 기록해 둔다 (종료할 때 되돌리려고)
            except Exception:
                pass
        self.moving[item["index"]] = {"x": item["x"], "y": item["y"], "vx": vx, "vy": vy,
                                      "px": round((item["x"] - self.origin[0]) * self.dpr),
                                      "py": round((item["y"] - self.origin[1]) * self.dpr)}

    def update(self, dt):
        if not self.moving:
            return
        l, t, r, b = self.bounds
        cw, ch = self.cell
        done = []
        for idx, m in self.moving.items():
            m["x"] += m["vx"] * dt
            m["y"] += m["vy"] * dt
            k = math.exp(-self.FRICTION * dt)
            m["vx"] *= k
            m["vy"] *= k
            if m["x"] < l:
                m["x"], m["vx"] = l, abs(m["vx"]) * 0.5
            elif m["x"] > r - cw:
                m["x"], m["vx"] = r - cw, -abs(m["vx"]) * 0.5
            if m["y"] < t:
                m["y"], m["vy"] = t, abs(m["vy"]) * 0.5
            elif m["y"] > b - ch:
                m["y"], m["vy"] = b - ch, -abs(m["vy"]) * 0.5
            px, py = round((m["x"] - self.origin[0]) * self.dpr), round((m["y"] - self.origin[1]) * self.dpr)
            if (px, py) != (m["px"], m["py"]):
                self.icons.set_position(idx, px, py)
                m["px"], m["py"] = px, py
            if math.hypot(m["vx"], m["vy"]) < 8:
                done.append(idx)
        for idx in done:
            del self.moving[idx]
            note = getattr(self.icons, "note_rest", None)
            if note:
                try:
                    note(idx)                         # 멈춘 자리를 기록 (사용자가 나중에 직접 옮겼는지 구분하려고)
                except Exception:
                    pass


# ---------------------------------------------------------------------------
class CatBrain:
    def __init__(self, world: World, pet, field: IconField, scale: float):
        self.world, self.pet, self.field = world, pet, field
        self.sc = scale
        self.cw, self.ch = 120 * scale, 105 * scale
        self.hold_drop = self.ch * 0.45     # 집어 올렸을 때 마우스에서 발바닥까지 거리
        self._travel = None                 # 다른 모니터로 걸어가는 중이면 목표 x
        self.x = world.start_x
        self.feet = world.floor
        self.on = None                      # 서 있는 창의 hwnd (None = 바닥)
        self.facing = 1
        self.vx = self.vy = 0.0
        self.v_now = 0.0                    # 지금 걷는 속도(크기): 목표 속도로 서서히 다가간다
        self._stopping = None               # 걷기가 끝나 멈추는 중이면 멈추기 시작한 시각(self.t)
        self.state = S.IDLE
        self.t = 0.0
        self.dur = 2.0
        self.life = 0.0
        self.landing = 0.0
        self.pending = None
        self.bubble = None                  # (text, until)
        self.kick_enabled = True
        self.an = Animator("stand")
        self._anim_state = None
        self._seg = None                    # JUMP/LEAP 보간 정보
        self._kick = None
        self._hold_hist = []
        self._next_chat = time.monotonic() + 40
        self.sleep_anim = SLEEP_ANIMS[0]
        self.gait = S.WALK
        self.stroke_until = 0.0
        self._pet_energy = 0.0
        self._last_stroke_mood = 0.0
        self.ball = None                    # 놀아주기 공 {x, v}
        self.play = None
        self.thinking = False               # 앱 런처가 열려 있어 '무엇을 할까' 생각하는 중
        self.last_kind = None               # 방금 한 행동 종류 (flow.py 의 흐름에서 다음 행동을 고르는 기준)
        self.mode = None                    # None(평소) / 'corner'(한쪽에서 쉬기) / 'night'(잠자는 시간)
        self.corner_side = 1                # 구석 위치: 1=오른쪽, -1=왼쪽
        self.hour_fn = lambda: time.localtime().tm_hour + time.localtime().tm_min / 60.0     # 시간대별 활발함 보정용
        self.on_fed = None                  # 밥을 다 먹었을 때 부르는 함수 (밥 시간 기록용)
        self.on_played = None               # 놀아주기가 끝났을 때 부르는 함수
        self.meal = False                   # 지금 먹는 것이 '밥 시간 밥'인가
        self.cursor_fn = None               # 마우스 커서의 화면 좌표 (x, y) 를 돌려주는 함수 (놀아주기(깃털)에서 쓴다. cat.py 가 정해 준다)
        self.tease = None                   # 놀아주기(깃털) 진행 정보 (없으면 None)
        self.mouse = None                   # 쥐 잡기 연출 중인 쥐 {x, dir, t0, fade, caught} (고양이 창이 그린다)
        self._hunt = None
        self._hunt_cb = None
        self.pending_force = False
        self.say("냐옹~")

    # --- 공통 ----------------------------------------------------------
    def say(self, text, secs=2.5):
        self.bubble = (text, time.monotonic() + secs)

    def go(self, state, dur=0.0):
        self.state, self.t, self.dur = state, 0.0, dur
        if state is not S.WALK:
            self._travel = None
        if state not in GROUND_MOVE:
            self.v_now = 0.0                        # 다른 동작으로 바뀌면 다음 걸음은 처음부터 서서히 빨라진다
        self._stopping = None

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, v):
        self._x = v
        self.world.cx = v                   # 월드의 바닥/좌우 한계는 고양이가 있는 모니터 기준

    def reset(self):
        """꼬이면 진행 중이던 일을 모두 버리고 현재 모니터 바닥에서 가만히 서 있는 상태로 되돌린다."""
        self._kick = self.ball = self.play = self.pending = self._travel = self._seg = self.tease = None
        self.on = None
        self.vx = self.vy = 0.0
        w = self.world
        a = min(w.areas, key=lambda r: 0.0 if r[0] <= self.x <= r[2] else min(abs(self.x - r[0]), abs(self.x - r[2])))
        self.x = min(max(self.x, a[0] + self.cw * 0.5), a[2] - self.cw * 0.5)
        self.feet = w.floor
        self.go(S.IDLE, 1.0)

    def relocate(self):
        """모니터 구성이 바뀐 뒤: 고양이가 화면 밖에 있으면 가장 가까운 모니터 바닥으로 데려온다."""
        w = self.world
        if any(a[0] <= self.x <= a[2] for a in w.areas) and self.feet <= w.bbox[3]:
            return
        a = min(w.areas, key=lambda r: min(abs(self.x - r[0]), abs(self.x - r[2])))
        self.x = min(max(self.x, a[0] + self.cw * 0.5), a[2] - self.cw * 0.5)
        self.on, self._kick, self.ball, self.play, self._travel = None, None, None, None, None
        self.feet = w.floor
        self.go(S.IDLE, 1.0)

    @property
    def hit_rect(self):
        return (self.x - self.cw / 2, self.feet - self.ch, self.cw, self.ch)

    def _clamp_x(self):
        w = self.world
        self.x = min(max(self.x, w.left + self.cw * 0.3), w.right - self.cw * 0.3)

    def _motion_speed(self):
        """동작 시간 배율: 평소 MOTION_SPEED(1.1). 나비잡기 놀이(그 사이의 점프·낙하 포함)와 종종걸음은 1.0 (속도를 그대로 둔다)."""
        if self.tease is not None or self.state is S.TEASE:
            return 1.0
        if self.state is S.WALK and self.gait is S.RUN:
            return 1.0
        return MOTION_SPEED

    # --- 매 프레임 -----------------------------------------------------
    def update(self, dt):
        w = self.world
        if not (math.isfinite(self.x) and math.isfinite(self.feet)) or self.feet > w.bbox[3] + 300 or self.feet < -600:
            self.reset()                            # 안전장치: 좌표가 화면 밖으로 멀리 벗어났거나 깨졌으면 현재 바닥에 다시 세운다
        self.world.refresh()
        self.pet.tick(dt)                           # 배고픔·기분은 실제 시간대로 (동작만 빠르게 한다)
        self.field.update(dt)
        dt *= self._motion_speed()
        self.t += dt
        self.life += dt
        self.landing = max(0.0, self.landing - dt)
        self._chat()
        prev_x = self.x
        getattr(self, "_st_" + self.state.name.lower())(dt)
        if self.tease is not None and self.state not in (S.TEASE, S.FALL, S.JUMP) and time.monotonic() >= self.tease["end"]:
            self.tease = None               # 놀아 주는 시간이 끝났는데 다른 동작 중(떨어지는 중 등)이면 그냥 끝낸다
        self._ball_update(dt)
        dist = abs(self.x - prev_x) if self.state in GROUND_MOVE else 0.0
        name, param, blend = self._anim_choice()
        self.an.play(name, blend=blend, restart=(self.state is not self._anim_state), **param)
        self._anim_state = self.state
        self.an.update(dt, dist / self.sc)

    def pose(self):
        """이번 프레임에 그릴 포즈 (공 같은 월드 소품 위치를 반영)."""
        p = self.an.pose()
        if self.ball and self.an.name != "bunny":
            p["ball"] = 1.0
            p["ballx"] = (self.ball["x"] - self.x) * self.facing / self.sc
            p["bally"] = 0.0
        return p

    def _anim_choice(self):
        s = self.state
        if s in (S.JUMP, S.KICK_LEAP):
            if self.t < self._seg["prep"]:
                return "crouch", {}, 0.15
            p = (self.t - self._seg["prep"]) / self._seg["dur"]
            down = 1 if self._seg["f1"] > self._seg["f0"] + 20 else 0       # 아래로 뛰어내리는 도약인가
            return "jump", {"p": min(1.0, p), "down": down}, 0.08
        if s is S.IDLE and self.landing > 0:
            return "land", {}, 0.12
        if s is S.SLEEP:
            return self.sleep_anim, {}, 0.5
        if s in (S.WALK,):
            return ("trot" if self.gait is S.RUN else "walk"), {}, 0.25
        if s is S.KICK_WALK:
            return "trot", {}, 0.2
        if s is S.KICK_HIT:
            return "swat", {}, 0.08
        if s is S.HUNT:
            return {"spot": ("sit_tilt", {}, 0.2), "chase": ("run", {}, 0.15), "pounce": ("swat", {}, 0.06), "proud": ("sit", {}, 0.3)}[self._hunt["phase"]]
        if s is S.TEASE:
            return self._tease_anim()
        if s is S.PLAY:
            ph = self.play["phase"]
            return {"wiggle": ("wiggle", {}, 0.25), "pounce": ("hop", {"p": min(1.0, self.t_phase() / 0.5)}, 0.06),
                    "bat": ("bat", {}, 0.06), "chase": ("run", {}, 0.2), "hug": ("bunny", {}, 0.3)}[ph]
        return STATE_ANIM.get(s, "stand"), {}, 0.3

    def _chat(self):
        now = time.monotonic()
        if now < self._next_chat or self.thinking or self.mode or self.state not in (S.IDLE, S.SIT, S.SITTILT, S.WALK, S.LOAF):
            return
        self._next_chat = now + random.uniform(40, 90)
        if self.pet.hungry:
            self.say(random.choice(["배고프당...옹~ 🐟", "밥 줘랑..옹~ 🐟", "냐아아…"]))
        elif self.pet.happy:
            self.say(random.choice(["♪ 랄라냐옹~", "냐옹~ ❤️", "😸 기분 좋다냐옹~"]))
        elif self.pet.mood < 30:
            self.say(random.choice(["… 냐앙…", "심심하당..옹~ 😿"]))

    # --- 발판 ----------------------------------------------------------
    def _stand(self):
        """서 있는 발판을 따라간다. 발판이 사라지면 False."""
        if self.on is None:
            self.feet = self.world.floor
            return True
        r = self.world.rect_of(self.on)
        if r is None or not (r[0] <= self.x <= r[2]) or r[1] < self.world.min_top:
            self._start_fall()
            return False
        self.feet = r[1]
        return True

    def _range(self):
        if self.on is None:
            w = self.world
            return w.left + self.cw * 0.3, w.right - self.cw * 0.3
        r = self.world.rect_of(self.on)
        return (r[0], r[2]) if r else (self.x, self.x)

    def _start_fall(self, vx=0.0, vy=0.0):
        self.on = None
        self.vx, self.vy = vx, vy
        self.go(S.FALL)

    def _land(self, top, hwnd):
        self.feet, self.on, self.vx, self.vy = top, hwnd, 0.0, 0.0
        self.landing = 0.3
        if self.tease is not None:                          # 놀아주던 중 떨어졌다(또는 아이콘에서 내려왔다) 내려앉았으면: 시간이 남았으면 다시 나비를 쫓고, 끝났으면 마무리
            if time.monotonic() < self.tease["end"]:
                self.tease.update(ph="run", pt=0.0, vx=0.0)
                self.go(S.TEASE)
                return
            return self._end_tease()
        self.go(S.IDLE, 0.4)

    # --- 쉬는/제자리 상태 ----------------------------------------------
    def _st_rest(self, dt):
        if not self._stand():
            return
        if self.t >= self.dur:
            self._after_rest()

    _st_groomleg = _st_scratchneck = _st_groomface = _st_idle = _st_sit = _st_sittilt = _st_loaf = _st_sleep = _st_groom = _st_yawn = _st_stretch = _st_scratch = _st_rest
    _st_knead = _st_tailplay = _st_rest

    def _after_rest(self):
        s = self.state
        if self.thinking and s is S.SITTILT:
            self.t = 0.0                    # 런처가 열려 있는 동안은 갸웃한 채로 기다린다
            return
        if s is S.SLEEP and not self.mode:
            self.say("후아암~ 누구냥.. 😺", 2.2)
        self._pick_next()                   # 다음 행동은 flow.py 의 흐름(FLOW)에서 고른다

    def _st_eat(self, dt):
        if self._stand() and self.t >= self.dur:
            self.pet.feed_meal() if self.meal else self.pet.feed()
            self.meal = False
            self.say("😋 맛있당..옹~", 2.0)
            self.last_kind = "eat"
            self.go(S.SIT, 3.0)
            if self.on_fed:
                self.on_fed()

    def _st_stroke(self, dt):
        if self._stand() and self.life > self.stroke_until:
            self.go(random.choice((S.SITTILT, S.SITTILT, S.SIT)), random.uniform(5, 9))

    def _st_held(self, dt):
        pass

    # --- 걷기/달리기/살금살금 ------------------------------------------
    def _move_speed(self):
        k = self.sc
        if self.state is S.RUN:
            return V_RUN * k
        if self.state is S.SNEAK:
            return V_SNEAK * k
        base = V_TROT if self.gait is S.RUN else V_WALK
        return base * k * (0.8 if self.pet.hungry else 1.0)

    def _locomote(self, dt, target=None):
        """걷기·달리기 한 프레임. target: 이번 목표 속도 (None 이면 지금 걸음의 속도, 0 이면 멈추는 중)."""
        if not self._stand():
            return False
        goal = self._move_speed() if target is None else target
        top = max(self._move_speed(), 1.0)
        if goal > self.v_now:
            self.v_now = min(goal, self.v_now + top / ACCEL_T * dt)
        else:
            self.v_now = max(goal, self.v_now - top / DECEL_T * dt)
        if self.v_now <= 0.0 and goal <= 0.0:
            return True
        self.x += self.facing * max(self.v_now, 0.0) * dt
        lo, hi = self._range()
        if self.x < lo or self.x > hi:
            if self.on is None and self._cross_ledge():
                return False
            if self.on is None or random.random() < 0.6:
                self.x = min(max(self.x, lo), hi)
                self.facing = -self.facing
                if self.state is S.WALK and self._travel is None:        # 끝에 닿으면 걷던 자세 그대로 뒤집지 않고, 멈춰 서서 돌아선다
                    self.v_now = 0.0
                    self._stopping = None
                    self.go(S.IDLE, random.uniform(0.6, 1.4))
                    return False
            else:
                self._start_fall(vx=self.facing * 80 * self.sc, vy=-120 * self.sc)    # 창 가장자리에서 폴짝
                return False
        return True

    def _cross_ledge(self):
        """바닥 높이가 다른 이웃 모니터로 건너간다: 이웃이 더 낮으면 가장자리에서 뛰어내리고, 더 높으면 뛰어오른다.
        건너가지 않으면 False (그러면 평소처럼 돌아선다)."""
        w = self.world
        for d, a in w.neighbors(self.x):
            if d != self.facing:
                continue
            if self._travel is None and random.random() > 0.3:
                continue
            drop = a[3] - w.floor                 # 양수: 이웃 바닥이 더 낮다(화면 아래)
            inside = a[0] + self.cw * 0.5 if d > 0 else a[2] - self.cw * 0.5
            if drop > 6:
                self.x = inside                    # 가장자리를 넘어가서 이웃 모니터 위에서 떨어진다
                self._start_fall(vx=d * 60 * self.sc, vy=-80 * self.sc)
                return True
            if -drop <= 560:
                rise = -drop
                self._begin_seg(S.JUMP, inside, a[3], 0.7 + rise / 1500, 70 + 0.2 * rise, None)
                return True
        self._travel = None
        return False

    def _st_walk(self, dt):
        tgt = self._travel
        if tgt is not None and self.state is S.WALK:
            if abs(tgt - self.x) < 14 * self.sc:
                self._travel = None
                return self._pick_next()
            self.facing = 1 if tgt >= self.x else -1
        if self.t < self.dur and self._stopping is None:
            self._locomote(dt)
            return
        if self._stopping is None:                  # 걷기가 끝났다: 바로 다른 자세로 바뀌지 않고 서서히 멈춘 다음
            self._stopping = self.t
        st0 = self.state                            # (달리기·살금살금도 이 함수를 같이 쓴다)
        moved = self._locomote(dt, 0.0)
        if not moved or self.state is not st0:      # 멈추는 사이 떨어지거나 돌아서는 등 다른 상태가 됐다
            self._stopping = None
            return
        if self.v_now <= 0.5 * self.sc or self.t - self._stopping >= STOP_MAX:
            self._stopping = None
            self.v_now = 0.0
            self._pick_next()

    def _start_travel(self):
        """다른 모니터 쪽으로 종종걸음으로 놀러 간다."""
        w = self.world
        if self.on is not None:
            return False
        others = w.other_areas(self.x)
        if others:
            a = random.choice(others)
            margin = self.cw * 0.5 + 60
            tx = random.uniform(a[0] + margin, a[2] - margin)
        else:                                       # 바닥 높이가 다른 이웃: 그쪽 가장자리까지 걸어가 건너간다
            ok = [(d, a) for d, a in w.neighbors(self.x) if a[3] - w.floor > 6 or w.floor - a[3] <= 560]
            if not ok:
                return False
            d, a = random.choice(ok)
            left, right, _, _ = w.strip_at(self.x)
            tx = (right if d > 0 else left) + d * (self.cw * 0.3 + 80)
        self.gait = S.RUN
        self.facing = 1 if tx >= self.x else -1
        self.go(S.WALK, 90.0)
        self._travel = tx
        return True

    _st_run = _st_sneak = _st_walk

    # --- 낙하 ----------------------------------------------------------
    def _st_fall(self, dt):
        w = self.world
        self.vy += G * self.sc * dt
        self.vx *= math.exp(-1.5 * dt)
        self.x += self.vx * dt
        self._clamp_x()
        f0 = self.feet
        f1 = f0 + self.vy * dt
        if f0 > w.floor + 1.5:                      # 모니터를 바꿔서 바닥이 위로 올라오면 고양이가 새 바닥보다 아래에 있게 된다: 그대로 두면 영영 떨어진다
            self._land(w.floor, None)
            return
        if self.vy >= 0:
            for top, hwnd in w.surfaces_below(self.x, f0):
                if top >= f0 - 1.5:
                    if top <= f1:
                        self._land(top, hwnd)
                        return
                    break
        self.feet = f1

    # --- 점프 (창 위로) ------------------------------------------------
    def _begin_seg(self, state, tx, tfeet, dur, arc, hwnd=None, prep=0.3):
        self._seg = {"x0": self.x, "f0": self.feet, "x1": tx, "f1": tfeet, "arc": arc, "hwnd": hwnd,
                     "dur": dur, "prep": prep}
        self.facing = 1 if tx >= self.x else -1
        self.on = None
        self.go(state, dur + prep)

    def _try_jump(self):
        cand = self.world.jump_targets(self.x, self.feet)
        if not cand:
            return False
        lx, top, hwnd = random.choice(cand)
        rise = self.feet - top
        self._begin_seg(S.JUMP, lx, top, 0.7 + rise / 1500, 70 + 0.2 * rise, hwnd)
        return True

    def _tween(self):
        s = self._seg
        tt = self.t - s["prep"]
        if tt < 0:                          # 웅크리는 동안은 제자리
            self.feet = s["f0"]
            return 0.0
        p = min(1.0, tt / s["dur"])
        self.x = s["x0"] + (s["x1"] - s["x0"]) * p
        self.feet = s["f0"] + (s["f1"] - s["f0"]) * p - 4 * s["arc"] * p * (1 - p)
        return p

    def _st_jump(self, dt):
        if self._tween() < 1.0 or self.t < self._seg["prep"]:
            return
        s = self._seg
        if s["hwnd"] is None:                       # 이웃 모니터 바닥으로 건너온 경우
            self._land(self.world.floor, None)
            return
        r = self.world.rect_of(s["hwnd"])
        if r and r[0] <= self.x <= r[2]:
            self._land(r[1], s["hwnd"])
        else:
            self._start_fall()

    # --- 아이콘 차기 ---------------------------------------------------
    def _try_kick(self):
        f = self.field
        if not (f.enabled and self.kick_enabled):
            return False
        f.scan()
        cand = f.candidates()
        if not cand:
            return False
        cw_cell, ch_cell = f.cell
        cand.sort(key=lambda it: abs(it["x"] + cw_cell / 2 - self.x) + abs(it["y"] - self.feet) * 0.5)
        item = random.choice(cand[:8])
        icx = item["x"] + cw_cell / 2
        icy = item["y"] + ch_cell * 0.4
        half = self.cw / 2
        w = self.world
        options = []
        for side, cx in ((1, icx - 12 - half), (-1, icx + 12 + half)):
            if w.left + self.cw * 0.3 <= cx <= w.right - self.cw * 0.3:
                options.append((abs(cx - self.x), side, cx))
        if not options:
            return False
        _, side, stand_x = min(options)
        feet_t = min(w.floor, max(self.ch * 0.9, icy + 25 * self.sc))
        on_ground = feet_t >= w.floor - 8
        self._kick = {"item": item, "stand_x": stand_x, "feet": w.floor if on_ground else feet_t,
                      "side": side, "launched": False, "ground": on_ground}
        self.say("🐾 에잇냐옹!", 1.2)
        if self.on is None and (on_ground or abs(stand_x - self.x) > 320 * self.sc):
            self.facing = 1 if stand_x > self.x else -1
            self.go(S.KICK_WALK, 12.0)
        else:
            self._start_leap()
        return True

    def _start_leap(self):
        k = self._kick
        dist = math.hypot(k["stand_x"] - self.x, k["feet"] - self.feet)
        self._begin_seg(S.KICK_LEAP, k["stand_x"], k["feet"], min(1.2, max(0.5, dist / 550 / self.sc)),
                        (50 + dist * 0.12), prep=0.25)
        self.facing = k["side"]

    def _st_kick_walk(self, dt):
        k = self._kick
        if not self._stand():
            self._kick = None
            return
        dx = k["stand_x"] - self.x
        self.facing = 1 if dx >= 0 else -1
        step = 160 * self.sc * dt
        if k["ground"]:
            if abs(dx) <= step:
                self.x = k["stand_x"]
                self.facing = k["side"]
                self.go(S.KICK_HIT)
            else:
                self.x += self.facing * step
        else:
            self.x += self.facing * step
            if abs(k["stand_x"] - self.x) <= 320 * self.sc:
                self._start_leap()
        if self.t > 12:
            self._kick = None
            self._pick_next()

    def _st_kick_leap(self, dt):
        if self._tween() >= 1.0 and self.t >= self._seg["prep"]:
            self.facing = self._kick["side"]
            self.go(S.KICK_HIT)

    def _st_kick_hit(self, dt):
        k = self._kick
        if not k["launched"] and self.t >= 0.3:
            k["launched"] = True
            self.field.launch(k["item"], k["side"] * random.uniform(750, 1150), random.uniform(-260, -40))
        if self.t >= 0.9:
            self._kick = None
            if self.feet < self.world.floor - 3 and not k["ground"]:
                self._start_fall()
            else:
                self.on = None
                self.go(S.IDLE, 1.0)

    # --- 놀아주기: 털실공 --------------------------------------------
    def t_phase(self):
        return self.t - self.play["t0"]

    def _play_phase(self, phase, **kw):
        self.play.update(phase=phase, t0=self.t, **kw)

    def _ball_update(self, dt):
        b = self.ball
        if not b:
            return
        b["x"] += b["v"] * dt
        b["v"] *= math.exp(-2.2 * dt)
        lo, hi = self._range() if self.state is S.PLAY or self.on is None else (self.world.left, self.world.right)
        lo, hi = lo + 10, hi - 10
        if b["x"] < lo or b["x"] > hi:
            b["x"] = min(max(b["x"], lo), hi)
            b["v"] = -b["v"] * 0.6

    def _start_play(self):
        self._kick = None
        lo, hi = self._range()
        d = 1 if (hi - self.x) > (self.x - lo) else -1
        self.facing = d
        self.ball = {"x": min(max(self.x + d * 150 * self.sc, lo + 20), hi - 20), "v": 0.0}
        self.play = {"phase": "wiggle", "t0": 0.0, "n": 0}
        self.say("🧶 털실이다냐옹~!", 2.0)
        self.go(S.PLAY)

    def _end_play(self):
        self.ball, self.play = None, None
        self.pet.play()
        self.say("😸 재밌냐옹~", 2.5)
        self.last_kind = "play"
        self.go(S.SIT, random.uniform(3, 5))
        if self.on_played:
            self.on_played()

    def _st_play(self, dt):
        if not self._stand():
            self.ball = self.play = None
            return
        pl, ball = self.play, self.ball
        tp = self.t_phase()
        sc = self.sc
        face = 1 if ball["x"] >= self.x else -1
        ph = pl["phase"]
        if ph == "wiggle":
            self.facing = face
            if tp >= (1.5 if pl["n"] == 0 else 0.7):
                lo, hi = self._range()
                tx = ball["x"] - face * 55 * sc
                self._seg = {"x0": self.x, "x1": min(max(tx, lo), hi), "f0": self.feet, "f1": self.feet,
                             "arc": 26 * sc, "dur": 0.5, "prep": 0.0, "hwnd": None}
                self._play_phase("pounce")
        elif ph == "pounce":
            s = self._seg
            p = min(1.0, tp / s["dur"])
            self.x = s["x0"] + (s["x1"] - s["x0"]) * p
            self.feet = s["f0"] - 4 * s["arc"] * p * (1 - p)
            if p >= 1.0:
                self.feet = s["f0"]
                self.landing = 0.0
                self._play_phase("bat")
        elif ph == "bat":
            if tp >= 0.34 and not pl.get("hit"):
                pl["hit"] = True
                ball["v"] = face * random.uniform(300, 480) * sc
            if tp >= 0.7:
                pl["hit"] = False
                self._play_phase("chase")
        elif ph == "chase":
            self.facing = 1 if ball["x"] >= self.x else -1
            self.x += self.facing * V_RUN * sc * dt
            lo, hi = self._range()
            self.x = min(max(self.x, lo), hi)
            near = abs(ball["x"] - self.x) < 75 * sc
            if (near and abs(ball["v"]) < 140 * sc) or tp > 4:
                pl["n"] += 1
                if pl["n"] >= 3:
                    self.facing = 1 if ball["x"] >= self.x else -1
                    self._play_phase("hug")
                else:
                    self._play_phase("wiggle")
        elif ph == "hug":
            ball["v"] = 0.0
            ball["x"] = self.x + self.facing * 60 * sc
            if tp >= 3.6:
                self._end_play()

    # --- 놀아주기(깃털): 마우스 커서가 나비 장난감이 되어 고양이가 쫓아다닌다 ----------------------
    # 단계(tease["ph"]): run(쫓기) → 나비가 가까워지면 높이에 따라 ─ 높다: crouch → air → land (뛰어올라 잡기, 화면 가운데 높이까지)
    #                                                           ─ 앉은 키 높이: swat (앞발로 툭툭)
    #                                                           ─ 낮다: wiggle → pounce → bat (엉덩이 씰룩 → 덮치기 → 바닥 치기)
    #                   나비가 높고 가까이에 바탕화면 아이콘이 있으면: 아이콘으로 뛰어올라(step) 아이콘을 밟고 거기서 다시 뛴다.
    def command_tease(self):
        if self._busy():
            self.pending = "tease"
            return
        self._start_tease()

    def tease_active(self):
        """놀아 주는 중이고 시간이 남았나 (cat.py 가 이 동안 마우스 커서를 나비로 바꿔 둔다)."""
        return self.tease is not None and time.monotonic() < self.tease["end"]

    @property
    def airborne(self):
        """발이 바닥에서 떠 있나 (그리개가 그림자·바닥 걸치기를 빼는 데 쓴다)."""
        return self.state in (S.JUMP, S.KICK_LEAP, S.FALL, S.HELD) or (self.state is S.TEASE and self.tease is not None and self.tease["ph"] in ("air", "step"))

    def _start_tease(self):
        if self.cursor_fn is None:
            return self._start_play()                       # 커서 위치를 알 수 없으면 공놀이로 대신
        self._kick = None
        self.ball = self.play = None
        self.thinking = False
        self.bubble = None
        self.mouse = self._hunt = None
        self.tease = {"end": time.monotonic() + TEASE_SEC, "ph": "run", "pt": 0.0, "vx": 0.0, "gait": "stand", "cool": 0.25, "plat": 0.0,
                      "engaged": False, "f": 0, "dur": 0.26, "h": 0.0, "base": self.feet, "vy": 0.0, "T": 1.0, "g": TEASE_G,
                      "icon": None, "goto": None, "icon_cool": 0.0, "icons": [], "icons_t": -9.0, "chk": 0.0, "seg": None}
        self.say("🦋 나비다냐옹!", 2.0)
        self.go(S.TEASE)

    def _end_tease(self):
        self.tease = None
        self.pet.play()
        self.say("😸 재밌냐옹~", 2.5)
        self.last_kind = "play"
        self.go(S.SIT, random.uniform(3, 5))
        if self.on_played:
            self.on_played()

    def _tease_anim(self):
        tz = self.tease
        if tz is None:
            return "stand", {}, 0.2
        ph = tz["ph"]
        if ph == "crouch":
            return "leap", {"f": 0}, 0.05
        if ph in ("air", "step"):
            return "leap", {"f": tz["f"]}, 0.03
        if ph == "land":
            return "land", {}, 0.05
        if ph == "wiggle":
            return "wiggle", {}, 0.08
        if ph == "pounce":
            return "hop", {"p": min(1.0, tz["pt"] / tz["dur"])}, 0.04
        if ph == "bat":
            return "bat", {}, 0.05
        if ph == "swat":
            return "swat", {}, 0.05
        return tz["gait"], {}, 0.12                         # "run" / "trot" / "walk" / "stand"

    def _tease_face(self, cx):
        d = cx - self.x
        if abs(d) > 6 * self.sc / 0.8:
            self.facing = 1 if d > 0 else -1

    def _tease_move(self, dt, k, tx, lo, hi):
        """목표 x 로 재빠르게 달려간다: 멀수록 빠르고(최고 TEASE_VMAX), 가까워지면 부드럽게 서고, 목표를 지나치지 않는다."""
        tz = self.tease
        dx = tx - self.x
        adx = abs(dx)
        dead = 9 * k
        vt = math.copysign(min(TEASE_VMAX * k, 7.0 * (adx - dead) + 30 * k), dx) if adx > dead else 0.0
        a = TEASE_ACC * k * dt
        vx = tz["vx"] + max(-a, min(a, vt - tz["vx"]))
        nx = self.x + vx * dt
        if (tx - self.x) * (tx - nx) < 0:                   # 목표를 지나치려 하면 거기서 선다
            nx, vx = tx, 0.0
        if nx < lo or nx > hi:
            nx, vx = min(max(nx, lo), hi), 0.0
        self.x, tz["vx"] = nx, vx
        if abs(vx) > 20 * k:
            self.facing = 1 if vx > 0 else -1               # 달리는 방향을 본다
        elif adx > 14 * k:
            self.facing = 1 if dx > 0 else -1
        sp, g = abs(vx) / k, tz["gait"]                     # 걸음 단계: 속도가 경계 근처에서 깜빡이지 않게 올라갈 때와 내려갈 때 경계를 다르게
        if sp > 235 or (g == "run" and sp > 175):
            tz["gait"] = "run"
        elif sp > 115 or (g == "trot" and sp > 75):
            tz["gait"] = "trot"
        elif sp > 14 or (g == "walk" and sp > 8):
            tz["gait"] = "walk"
        else:
            tz["gait"] = "stand"

    # --- 아이콘 디딤돌 ---------------------------------------------------------
    def _tease_icons(self):
        """밟고 뛸 수 있는 바탕화면 아이콘들: [(가운데 x, 윗면 y, 아이콘 번호, 칸 x, 칸 y)] (창에 가려진 것은 뺀다). 아이콘 위치를 읽는 일이라 3초에 한 번만 다시 읽는다."""
        tz = self.tease
        now = time.monotonic()
        if now - tz["icons_t"] < 3.0:
            return tz["icons"]
        tz["icons_t"] = now
        tz["icons"] = []
        f = self.field
        try:
            if not f.enabled:
                return tz["icons"]
            f.scan()
            cw, chh = f.cell
            for it in f.items:
                if it["index"] in f.moving:
                    continue
                ix, top = it["x"] + cw / 2, it["y"] + 0.1 * chh      # 아이콘 그림의 윗면 (칸 위쪽 조금 안쪽)
                if any(w.left <= ix <= w.right and w.top <= top <= w.bottom for w in self.world.wins):
                    continue                                        # 창이 가린 아이콘은 밟지 않는다
                tz["icons"].append((ix, top, it["index"], it["x"], it["y"]))
        except Exception:
            tz["icons"] = []
        return tz["icons"]

    def _tease_pick_icon(self, k, cx, cy, skip=None):
        """나비가 높이 있을 때 발판으로 삼을 아이콘: 오를 수 있는 높이에 있고, 나비 쪽으로 더 가까워지고, 나비 아래 가까이에 있는 것."""
        best = None
        lo, hi = self._range()
        for ix, top, idx, gx, gy in self._tease_icons():
            if idx == skip:
                continue
            up, rem = self.feet - top, top - cy                     # 지금 발에서 아이콘까지 / 아이콘에서 나비까지
            if not (30 * k <= up <= 230 * k and 50 * k <= rem <= (TEASE_LEAP_MAX + TEASE_REACH_AIR) * k and abs(ix - cx) <= 120 * k and lo <= ix <= hi):
                continue
            score = abs(ix - cx) + 0.3 * abs(ix - self.x)
            if best is None or score < best[0]:
                best = (score, ix, top, idx, gx, gy)
        return best[1:] if best else None

    def _tease_start_step(self, k, pick):
        """아이콘 pick=(가운데 x, 윗면 y, 번호, 칸 x, 칸 y) 으로 뛰어오른다."""
        ix, top, idx, gx, gy = pick
        up = self.feet - top
        self.tease.update(ph="step", pt=0.0, f=0, goto=None, vx=0.0, gait="stand",
                          seg={"x0": self.x, "f0": self.feet, "x1": ix, "f1": top, "arc": 0.3 * up + 28 * k, "dur": 0.4 + up / 1300.0,
                               "ic": {"ix": ix, "top": top, "idx": idx, "gx": gx, "gy": gy}})

    def _tease_icon_ok(self, ic):
        """밟고 있는 아이콘이 아직 그 자리에 있나 (사용자가 옮겼으면 False)."""
        f = self.field
        icons = getattr(f, "icons", None)
        if icons is None:
            return True
        try:
            px, py = icons.position(ic["idx"])
            x, y = px / f.dpr + f.origin[0], py / f.dpr + f.origin[1]
            return abs(x - ic["gx"]) <= 6 and abs(y - ic["gy"]) <= 6
        except Exception:
            return False

    def _tease_stand(self):
        """서 있는 발판을 따라간다: 아이콘 위면 아이콘 윗면, 아니면 바닥·창 윗변."""
        tz = self.tease
        ic = tz["icon"]
        if ic is None:
            return self._stand()
        self.feet = ic["top"]
        tz["chk"] += 1
        if tz["chk"] % 12 == 0 and not self._tease_icon_ok(ic):   # 아이콘이 없어졌거나 옮겨졌다 → 떨어진다
            tz["icon"] = None
            self._start_fall(vx=0.0, vy=-60 * self.sc / 0.8)
            return False
        return True

    def _tease_range(self):
        ic = self.tease["icon"]
        if ic is not None:
            k = self.sc / 0.8
            return ic["ix"] - 16 * k, ic["ix"] + 16 * k
        return self._range()

    def _tease_leave_icon(self, side):
        tz = self.tease
        k = self.sc / 0.8
        tz["icon"] = None
        tz["icon_cool"] = 1.5
        self.facing = side
        self._start_fall(vx=side * 140 * k, vy=-100 * k)

    # --- 한 프레임 ---------------------------------------------------------------
    def _st_tease(self, dt):
        tz = self.tease
        if tz is None or self.cursor_fn is None:
            return self._end_tease()
        k = self.sc / 0.8
        tz["pt"] += dt
        tz["cool"] = max(0.0, tz["cool"] - dt)
        tz["plat"] = max(0.0, tz["plat"] - dt)
        tz["icon_cool"] = max(0.0, tz["icon_cool"] - dt)
        ph = tz["ph"]
        if ph == "air":
            return self._tease_air(dt, k)
        if ph == "step":
            return self._tease_step(k)
        if not self._tease_stand():                         # 서 있던 창·아이콘이 사라졌다 → 떨어진다 (내려앉으면 _land 가 다시 이어 준다)
            return
        if time.monotonic() >= tz["end"] and ph in ("run", "land"):
            if tz["icon"] is not None:                      # 아이콘 위에서 시간이 끝났다: 먼저 바닥으로 내려온 뒤 마무리한다 (_land)
                return self._tease_leave_icon(self.facing or 1)
            return self._end_tease()                        # 시간이 다 됐다 (뛰는 중이면 내려앉은 뒤에)
        cx, cy = self.cursor_fn()
        lo, hi = self._tease_range()
        if ph == "crouch":                                  # 뛰기 직전 웅크림
            self._tease_face(cx)
            if tz["pt"] >= 0.11:
                h = tz["h"]
                g = max(TEASE_G * k, 8.0 * h / TEASE_AIR_T ** 2)       # 높이 뛸수록 중력도 세게: 아무리 높이 뛰어도 공중에 0.85초쯤만 떠 있어 날쌔다
                tz.update(ph="air", pt=0.0, vy=-math.sqrt(2 * g * h), base=self.feet, T=2 * math.sqrt(2 * h / g), f=1, g=g)
            return
        if ph == "land":
            if tz["pt"] >= 0.16:
                tz.update(ph="run", pt=0.0, cool=0.08)
            return
        if ph in ("wiggle", "pounce", "bat", "swat"):
            return self._tease_action(k, cx, hi, lo)
        self._tease_chase(dt, k, cx, cy, lo, hi)

    def _tease_chase(self, dt, k, cx, cy, lo, hi):
        tz = self.tease
        r = self.feet - cy                                  # 양수: 나비가 발바닥보다 위에 있다
        # (0) 아이콘 위에 서 있으면: 나비가 아직 높이 있고 가까이 있을 때만 머물며 뛴다. 아니면 나비 쪽으로 뛰어내린다
        ic = tz["icon"]
        if ic is not None:
            if r < 90 * k or abs(cx - ic["ix"]) > 130 * k:
                return self._tease_leave_icon(1 if cx > self.x else -1)
            if tz["cool"] <= 0 and r >= 150 * k:                # 위에 또 밟을 아이콘이 있으면 계단처럼 한 칸 더 올라간다
                nxt = self._tease_pick_icon(k, cx, cy, skip=ic["idx"])
                if nxt is not None:
                    return self._tease_start_step(k, nxt)
            self._tease_move(dt, k, min(max(cx, lo), hi), lo, hi)
            if tz["cool"] <= 0:
                self._tease_begin_action(k, cx, r)
            return
        # (1) 창 위에 있는데 나비가 창 밖 아래쪽에 있으면: 가까운 가장자리로 가서 뛰어내린다
        if self.on is not None and cy - self.feet > 110 * k:
            wr = self.world.rect_of(self.on)
            if wr is not None and not (wr[0] <= cx <= wr[2] and cy <= wr[3]):
                side = (1 if (hi - self.x) < (self.x - lo) else -1) if lo <= cx <= hi else (1 if cx > hi else -1)
                tx = hi - 4 * k if side > 0 else lo + 4 * k
                self._tease_move(dt, k, tx, lo, hi)
                if abs(self.x - tx) < 10 * k:
                    self.facing = side
                    self._start_fall(vx=side * 150 * k, vy=-130 * k)
                return
        # (2) 뛰어도 닿지 않을 만큼 높이 있으면 나비에 더 가까운 창 위로 올라간다
        if r > (TEASE_LEAP_MAX + TEASE_REACH_AIR + 20) * k and tz["plat"] <= 0:
            tz["plat"] = 1.2
            if self._tease_climb(cx, cy):
                return
        # (3) 나비가 높고 가까이에 바탕화면 아이콘이 있으면 그것을 밟고 뛴다 (바닥에 있을 때만)
        if self.on is None and r >= 150 * k and tz["icon_cool"] <= 0:
            goto = tz["goto"]
            pick = self._tease_pick_icon(k, cx, cy)
            if pick is None:
                tz["goto"], tz["icon_cool"] = None, 0.4
            else:
                if goto is None or goto[2] != pick[2]:
                    tz["goto"] = goto = pick
                ix, top = goto[0], goto[1]
                self._tease_move(dt, k, ix, lo, hi)
                if abs(self.x - ix) <= 14 * k and abs(tz["vx"]) < 80 * k:
                    self._tease_start_step(k, goto)
                return
        else:
            tz["goto"] = None
        # (4) 나비 아래로 달려간다. 가까워지면(들어갈 때 34, 나갈 때 58 로 경계를 달리해서 떨리지 않게) 높이에 맞는 동작을 한다
        self._tease_move(dt, k, cx, lo, hi)
        adx = abs(cx - self.x)
        band = (58 if tz["engaged"] else 34) * k
        tz["engaged"] = adx <= band
        if tz["engaged"] and abs(tz["vx"]) < 70 * k and tz["cool"] <= 0:
            self._tease_begin_action(k, cx, r)

    def _tease_begin_action(self, k, cx, r):
        tz = self.tease
        self._tease_face(cx)
        tz["vx"], tz["gait"] = 0.0, "stand"
        if r >= TEASE_REACH_STAND * k:                      # 높다 → 뛴다 (앞발이 나비에 닿을 높이만큼만)
            tz.update(ph="crouch", pt=0.0, h=max(18 * k, min(TEASE_LEAP_MAX * k, r - (TEASE_REACH_AIR - 15) * k)))
        elif r >= 25 * k:                                   # 앉은 키 높이 → 앞발로 툭툭
            tz.update(ph="swat", pt=0.0)
        else:                                               # 바닥 근처 → 엉덩이 씰룩, 덮치기
            tz.update(ph="wiggle", pt=0.0)

    def _tease_action(self, k, cx, hi, lo):
        tz = self.tease
        ph, pt = tz["ph"], tz["pt"]
        self._tease_face(cx)
        if ph != "pounce" and abs(cx - self.x) > 110 * k:   # 나비가 멀리 달아났다: 하던 동작을 접고 다시 쫓는다
            tz.update(ph="run", pt=0.0)
            return
        if ph == "wiggle":
            if pt >= 0.24:
                tz.update(ph="pounce", pt=0.0, x0=self.x, x1=min(max(cx - self.facing * 28 * k, lo), hi), dur=0.26)
        elif ph == "pounce":
            p = min(1.0, pt / tz["dur"])
            self.x = tz["x0"] + (tz["x1"] - tz["x0"]) * (1.0 - (1.0 - p) ** 2)
            self.feet -= 4 * 22 * k * p * (1 - p)           # 살짝 뛰어 덮친다
            if p >= 1.0:
                tz.update(ph="bat", pt=0.0)
        elif ph == "bat":
            if pt >= 0.6:
                tz.update(ph="run", pt=0.0, cool=0.12)
        elif ph == "swat":
            if pt >= 0.74:
                tz.update(ph="run", pt=0.0, cool=0.1)

    def _tease_air(self, dt, k):
        tz = self.tease
        cx, cy = self.cursor_fn()
        tz["vy"] += tz["g"] * dt
        self.feet += tz["vy"] * dt
        u = tz["pt"] / max(tz["T"], 0.2)
        tz["f"] = 1 if u < 0.14 else 2 if u < 0.64 else 4 if u < 0.82 else 5       # 사진 컷: 박차기 → 쭉 뻗기 → 앞발 들기 → 내려오며 앞발 들기
        on_icon = tz["icon"] is not None
        lo, hi = (self.world.left + 20 * k, self.world.right - 20 * k) if on_icon else self._range()     # 아이콘에서 뛸 때는 나비 쪽으로 몸이 자유롭게 날아간다
        dx = cx - self.x
        self.x = min(max(self.x + max(-320 * k, min(320 * k, dx * 7.0)) * dt, lo), hi)     # 공중에서도 나비 쪽으로 몸을 틀어 따라간다
        if abs(dx) > 8 * k:
            self.facing = 1 if dx > 0 else -1
        if tz["vy"] > 0 and self.feet >= tz["base"]:
            self.feet = tz["base"]
            if on_icon:
                ic = tz["icon"]
                if abs(self.x - ic["ix"]) > 20 * k:         # 아이콘에서 벗어난 곳에 내려왔다: 아이콘 옆으로 떨어져 바닥으로
                    tz["icon"] = None
                    tz.update(ph="run", pt=0.0, vx=0.0)
                    self._start_fall(vx=0.0, vy=0.0)
                    return
                self.x = min(max(self.x, ic["ix"] - 16 * k), ic["ix"] + 16 * k)
            tz.update(ph="land", pt=0.0, vx=0.0)

    def _tease_step(self, k):
        """아이콘 윗면으로 뛰어오른다: 웅크렸다가(0.1초) 포물선으로 날아가 아이콘 가운데에 내려앉는다."""
        tz = self.tease
        sg = tz["seg"]
        t = tz["pt"] - 0.1
        self._tease_face(sg["x1"])
        if t < 0:                                           # 웅크림
            tz["f"] = 0
            return
        p = min(1.0, t / sg["dur"])
        self.x = sg["x0"] + (sg["x1"] - sg["x0"]) * p
        self.feet = sg["f0"] + (sg["f1"] - sg["f0"]) * p - 4 * sg["arc"] * p * (1 - p)
        tz["f"] = 1 if p < 0.2 else 2 if p < 0.75 else 4
        if p >= 1.0:
            self.feet = sg["f1"]
            tz.update(ph="land", pt=0.0, vx=0.0, icon=sg["ic"], seg=None, cool=0.0)

    def _tease_climb(self, cx, cy):
        """나비가 너무 높으면: 나비에 가까운 높이의 창 윗변으로 뛰어오른다. 올라갈 곳이 없으면 False."""
        best = None
        for lx, top, hwnd in self.world.jump_targets(self.x, self.feet):
            w = next((w for w in self.world.wins if w.hwnd == hwnd), None)
            if w is None:
                continue
            gap = abs(top - cy)
            if gap < (self.feet - cy) * 0.75:               # 지금보다 확실히 나비에 가까워지는 곳만
                score = gap + 0.6 * max(0.0, w.left - cx, cx - w.right)
                if best is None or score < best[0]:
                    best = (score, lx, top, hwnd)
        if best is None:
            return False
        _, lx, top, hwnd = best
        rise = self.feet - top
        self.tease.update(ph="run", pt=0.0, vx=0.0)
        self._begin_seg(S.JUMP, lx, top, 0.5 + rise / 2200, 60 + 0.2 * rise, hwnd, prep=0.15)
        return True

    # --- 사용자 명령 ---------------------------------------------------
    def _busy(self):
        return self.state in (S.HELD, S.FALL, S.JUMP, S.KICK_LEAP, S.KICK_HIT, S.TEASE)

    def is_busy(self):
        return self._busy()

    def command_feed(self, force=False):
        """force=True: 밥 시간이라 배가 불러도 먹는다."""
        if self.pet.is_full and not force:
            self.say("배부르당..옹~ 😾")
            return
        if self._busy():
            self.pending = "feed"
            self.pending_force = force
            return
        self._start_eat(force)

    def command_play(self):
        if self._busy():
            self.pending = "play"
            return
        self._start_play()

    def _start_eat(self, force=False):
        self.meal = force
        self._kick = None
        self.ball = self.play = None
        self.say("🐟 냠냠냥~", 4.0)
        self.go(S.EAT, EAT_SEC)

    def stroke(self):
        """쓰다듬기 (클릭 또는 마우스를 몸 위에서 쓱쓱). 호출될 때마다 골골송 시간이 늘어난다."""
        now = self.life
        if now - self._last_stroke_mood > 1.2:
            self.pet.stroke()
            self._last_stroke_mood = now
        self.stroke_until = now + 1.3
        if self.state in (S.HELD, S.FALL, S.JUMP, S.KICK_LEAP, S.KICK_HIT, S.PLAY, S.EAT, S.TEASE):
            return
        if self.state is not S.STROKE:
            if self.state is S.SLEEP:
                self.say("…😾 깨웠냐옹…", 1.2)
            self._kick = None
            self.go(S.STROKE)
        self.say("❤️ 좋다냐옹~", 1.4)

    def hover(self, moved_px: float, inside: bool, dt: float):
        """마우스가 고양이 몸 위에서 움직이는 양으로 쓰다듬기를 감지한다."""
        if self.thinking or self.state is S.TEASE:
            return                          # 런처로 마우스를 옮기느라 몸 위를 지날 때 쓰다듬기로 오인하지 않게
        self._pet_energy = max(0.0, self._pet_energy - 260 * dt)
        if inside and self.state is not S.HELD:
            self._pet_energy += moved_px
            if self._pet_energy > 140:
                self._pet_energy = 140
                self.stroke()

    # --- 앱 런처: 클릭하면 '무엇을 할까' 생각하는 자세로 ------------------
    def think(self, on: bool):
        """on=True: 몸 세우고 앉아 갸웃(sit_tilt)한 채로 기다린다. on=False: 잠시 뒤 평소 행동으로 돌아간다."""
        if on:
            if self._busy():
                return
            self._kick = None
            self.ball = self.play = None
            self.bubble = None
            self.thinking = True
            self.go(S.SITTILT, 3600.0)
        elif self.thinking:
            self.thinking = False
            if self.state is S.SITTILT:
                self.dur = self.t + 1.5       # 1.5초 뒤 평소 행동을 고른다

    # --- 집어 올리기 ---------------------------------------------------
    def grab(self):
        self.mouse = self._hunt = self.tease = None
        self.thinking = False
        self._kick = None
        self.ball = self.play = None
        self.on = None
        self.go(S.HELD)
        self._hold_hist = []
        self.say("냥?! 뭐냐옹?!", 1.5)

    def hold(self, cx, cy):
        self.x = cx
        self.feet = cy + self.hold_drop            # 마우스가 고양이 목덜미 쪽에 오도록 (그리개마다 고양이 키가 달라서 바깥에서 정한다)
        self._hold_hist = (self._hold_hist + [(time.monotonic(), cx)])[-6:]

    def release(self):
        vx = 0.0
        h = self._hold_hist
        if len(h) >= 2 and h[-1][0] > h[0][0]:
            vx = max(-700.0, min(700.0, (h[-1][1] - h[0][1]) / (h[-1][0] - h[0][0])))
        self._start_fall(vx=vx)

    # --- 쥐 잡기 (경비 경보 연출) ------------------------------------------------
    def hunt(self, on_caught=None):
        """쥐가 나타나 고양이가 쫓아가서 앞발로 잡는다. 끝나면 on_caught() 를 부른다. 점프·낙하·집어 올림 중이면 끝난 뒤에."""
        if self.state in (S.HELD, S.FALL, S.JUMP, S.KICK_LEAP):
            self.pending, self._hunt_cb = "hunt", on_caught
            return
        self._kick = None
        self.ball = self.play = None
        self.tease = None                                   # 놀아주던 중이면 그만두고 쥐부터 (경보가 먼저)
        self.thinking = False
        self.bubble = None
        lo, hi = self._range()
        d = self.facing or 1
        if (d > 0 and self.x + 130 * self.sc > hi - 10) or (d < 0 and self.x - 130 * self.sc < lo + 10):
            d = -d                                          # 벽 쪽이면 반대편에서 쥐가 나타난다
        self.facing = d
        self.mouse = {"x": self.x + d * 100 * self.sc, "dir": d, "t0": time.monotonic(), "fade": 0.0, "caught": False}
        self._hunt = {"phase": "spot", "cb": on_caught}
        self.say("쥐다!", 1.6)
        self.go(S.HUNT)

    def _st_hunt(self, dt):
        h, m = self._hunt, self.mouse
        if h is None or m is None:
            return self.go(S.SIT, 1.0)
        if not self._stand():
            self.mouse = self._hunt = None
            return
        ph = h["phase"]
        lo, hi = self._range()
        if ph == "spot":                                    # 쥐를 발견하고 귀를 쫑긋
            m["fade"] = min(1.0, self.t / 0.3)
            if self.t >= 0.75:
                h["phase"] = "chase"
                self.t = 0.0
        elif ph == "chase":                                 # 쥐는 달아나고 고양이는 쫓아간다
            m["x"] = min(max(m["x"] + m["dir"] * V_RUN * 0.5 * self.sc * dt, lo + 6), hi - 6)
            self.facing = 1 if m["x"] >= self.x else -1
            self.x += self.facing * V_RUN * self.sc * dt
            self.x = min(max(self.x, lo), hi)
            if abs(m["x"] - self.x) < 46 * self.sc or self.t > 3.5:
                h["phase"] = "pounce"
                self.t = 0.0
        elif ph == "pounce":                                # 앞발로 탁!
            self.facing = 1 if m["x"] >= self.x else -1
            if self.t >= 0.28 and not m["caught"]:
                m["caught"] = True
                m["t0"] = time.monotonic()
            if self.t >= 0.55:
                h["phase"] = "proud"
                self.t = 0.0
                self.say("잡았다옹!", 2.2)
        elif ph == "proud":                                 # 뿌듯
            if self.t >= 1.6:
                cb = h.get("cb")
                self.mouse = self._hunt = None
                self.last_kind = "kick"
                self.go(S.SIT, 2.5)
                if cb:
                    cb()

    # --- 모드: 한쪽에서 쉬기 / 잠자는 시간 -------------------------------------
    def set_mode(self, mode):
        """None(평소) / 'corner'(구석으로 가서 쉬기) / 'night'(구석에서 웅크리고 잠). 바뀌면 하던 일을 끊고 바로 따라간다."""
        if mode == self.mode:
            return
        self.mode = mode
        if self.thinking or self.state in (S.HELD, S.FALL, S.JUMP, S.KICK_LEAP, S.KICK_HIT, S.PLAY, S.EAT, S.STROKE, S.TEASE):
            return                          # 이 동작들이 끝나면 자연스럽게 새 모드로 간다
        self._kick = None
        self.ball = self.play = None
        if mode is None and self.state is S.SLEEP:
            self.say("후아암~ 누구냥.. 😺", 2.2)
        self._pick_next()

    def _corner_x(self):
        lo, hi = self.world.left + self.cw * 0.3, self.world.right - self.cw * 0.3
        return hi - 6 * self.sc if self.corner_side > 0 else lo + 6 * self.sc

    def _go_to_corner(self):
        """구석까지 걸어간다 (창 위에 있으면 먼저 폴짝 내려온다). 이미 도착해 있으면 True."""
        if self.on is not None:
            self.facing = self.corner_side
            self._start_fall(vx=self.corner_side * 60 * self.sc, vy=-100 * self.sc)
            return False
        tx = self._corner_x()
        dx = tx - self.x
        if abs(dx) <= 14 * self.sc:
            return True
        self.gait = S.RUN if abs(dx) > 500 * self.sc else S.WALK
        self.facing = 1 if dx > 0 else -1
        self.go(S.WALK, 120.0)
        self._travel = tx
        self.last_kind = "travel"
        return False

    # --- 다음 행동 선택 ------------------------------------------------
    def _allowed(self):
        """지금 할 수 있는 행동 종류 (점프할 창이 없으면 점프 제외 등)."""
        ok = set(flow.KINDS)
        if not self.world.jump_targets(self.x, self.feet):
            ok.discard("jump")
        if not (self.on is None and (self.world.other_areas(self.x) or self.world.neighbors(self.x))):
            ok.discard("travel")
        if not (self.field.enabled and self.kick_enabled):
            ok.discard("kick")
        return ok

    def _mult(self):
        """기분·배고픔·시간대에 따른 가중치 배수."""
        p = self.pet
        hungry, happy, sad = p.hungry, p.happy, p.mood < 30
        move, nap = flow.activity_mult(self.hour_fn())
        m = {}
        for k in ("walk", "trot", "run", "sneak", "jump", "travel", "kick", "tailplay", "knead"):
            m[k] = move * (1.4 if happy else 1.0)
        m["sleep"] = nap * (1.5 if sad else 0.7 if hungry else 1.0)
        if hungry or sad:
            for k in ("run", "kick", "tailplay", "knead", "trot"):
                m[k] = 0.0
        return m

    def _pick_next(self):
        p = self.pet
        if self.pending:
            cmd, self.pending = self.pending, None
            force, self.pending_force = self.pending_force, False
            if cmd == "feed" and (force or not p.is_full):
                return self._start_eat(force)
            if cmd == "play":
                return self._start_play()
            if cmd == "tease":
                return self._start_tease()
            if cmd == "hunt":
                return self.hunt(self._hunt_cb)
        if self.mode and not self._go_to_corner():
            return                          # 구석으로 가는 중 (도착하면 다시 이 함수가 불린다)
        if self.mode == "night":
            self.facing = -self.corner_side
            self.sleep_anim = "sleep_curl"  # 웅크리고 자기
            self.last_kind = "sleep"
            return self.go(S.SLEEP, 600.0)
        if self.mode == "corner":
            self.facing = -self.corner_side                    # 화면 안쪽을 본다
            kind = flow.choose(self.last_kind, flow.WEIGHTS_CORNER, set(flow.CORNER_KINDS))
        else:
            kind = flow.choose(self.last_kind, flow.WEIGHTS_DAY, self._allowed(), self._mult())
        self._start_kind(kind)

    def _start_kind(self, kind):
        """고른 행동을 시작한다 (실패하면 걷기로 대신)."""
        if kind == "kick" and not self._try_kick():
            kind = "walk"
        elif kind == "jump" and not self._try_jump():
            kind = "walk"
        elif kind == "travel" and not self._start_travel():
            kind = "walk"
        self.last_kind = kind
        if kind in ("kick", "jump", "travel"):
            return                          # 각자의 시작 함수가 이미 상태를 정했다
        d = flow.duration(kind)
        if kind in ("walk", "trot"):
            self.facing = random.choice((-1, 1))
            self.gait = S.RUN if kind == "trot" else S.WALK
            self.go(S.WALK, d)
        elif kind == "run":
            self.facing = random.choice((-1, 1))
            self.go(S.RUN, d)
            self.say("우다다다냐옹!", 2)
        elif kind == "sneak":
            self.facing = random.choice((-1, 1))
            self.go(S.SNEAK, d)
        elif kind == "sleep":
            self.say("골골~ 💤", 4)
            self.sleep_anim = random.choice(SLEEP_ANIMS)
            self.go(S.SLEEP, d)
        elif kind == "knead":
            self.say("냥이펀치 냥이펀치 꾹꾹이~ 🐾", 2.8)
            self.go(S.KNEAD, d)
        else:
            self.go({"idle": S.IDLE, "sit": S.SIT, "sittilt": S.SITTILT, "loaf": S.LOAF, "groom": S.GROOM, "groomface": S.GROOMFACE,
                     "groomleg": S.GROOMLEG, "scratchneck": S.SCRATCHNECK, "scratch": S.SCRATCH, "yawn": S.YAWN, "stretch": S.STRETCH,
                     "tailplay": S.TAILPLAY}[kind], d)
