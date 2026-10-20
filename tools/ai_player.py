"""잘라 낸 AI 동작 컷(assets/ai)을 반복 재생해 보는 미리보기 웹페이지를 만든다. (개발용 도구)

결과: preview/ai_player.html  (더블클릭으로 열면 됨. 그림은 assets/ai 의 파일을 그대로 불러옴)
컷마다 발바닥 높이(맨 아래)를 맞추고, 가로 중심은 고양이 몸 무게중심에 맞춘다. 컷 사이를 부드럽게 섞는 것도 켤 수 있다.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
AI = ROOT / "assets" / "ai"
OUT = ROOT / "preview" / "ai_player.html"


def collect():
    acts = []
    for d in sorted(AI.iterdir()):
        if not (d / "meta.json").exists():
            continue
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        frames = []
        for fr in meta["frames"]:
            im = Image.open(d / fr["file"])
            a = np.array(im)[..., 3] > 40
            ys, xs = np.where(a)
            # 몸 무게중심: 꼬리·뻗은 발에 휘둘리지 않게 가운데 부분(25~75% 구간)의 중심을 쓴다
            lo, hi = np.percentile(ys, [20, 100])
            sel = (ys >= lo)
            cx = float(xs[sel].mean()) if sel.any() else im.width / 2
            frames.append({"src": f"../assets/ai/{d.name}/{fr['file']}", "w": im.width, "h": im.height, "cx": round(cx, 1)})
        acts.append({"name": d.name, "frames": frames})
    return acts


HTML = """<!doctype html><html lang="ko"><meta charset="utf-8"><title>AI 고양이 동작 미리보기</title>
<style>
body{font-family:'Malgun Gothic',sans-serif;background:#2b3a33;color:#eee;margin:0;padding:14px}
h1{font-size:18px;margin:0 0 8px}.bar{display:flex;gap:18px;flex-wrap:wrap;align-items:center;margin-bottom:12px;font-size:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}
.card{background:#1f2b26;border-radius:8px;padding:6px}.card canvas{width:100%;display:block;background:#33463d;border-radius:6px}
.t{font-size:13px;margin:4px 2px 0}
</style>
<h1>AI 고양이 동작 미리보기 (6컷 반복 재생)</h1>
<div class="bar">
 <label>한 컷 시간 <input id="ms" type="range" min="60" max="600" value="180"> <b id="msv">180</b>ms</label>
 <label><input id="blend" type="checkbox"> 컷 사이 부드럽게 섞기</label>
 <label><input id="pingpong" type="checkbox"> 왔다갔다 재생(앞→뒤→앞)</label>
</div>
<div class="grid" id="g"></div>
<script>
const ACTS=__DATA__;
const g=document.getElementById('g'),ms=document.getElementById('ms'),msv=document.getElementById('msv');
const blend=document.getElementById('blend'),pp=document.getElementById('pingpong');
ms.oninput=()=>msv.textContent=ms.value;
const cards=ACTS.map(a=>{
  const maxL=Math.max(...a.frames.map(f=>f.cx)),maxR=Math.max(...a.frames.map(f=>f.w-f.cx)),maxH=Math.max(...a.frames.map(f=>f.h));
  const W=Math.ceil(maxL+maxR)+16,H=maxH+16;
  const c=document.createElement('canvas');c.width=W;c.height=H;
  const d=document.createElement('div');d.className='card';d.appendChild(c);
  const t=document.createElement('div');t.className='t';t.textContent=a.name.replace(/^\\d+-/,'');d.appendChild(t);g.appendChild(d);
  const imgs=a.frames.map(f=>{const i=new Image();i.src=f.src;return i});
  return {a,c,ctx:c.getContext('2d'),imgs,W,H,maxL};
});
function draw(k,i,alpha){
  const f=k.a.frames[i],im=k.imgs[i];if(!im.complete)return;
  k.ctx.globalAlpha=alpha;k.ctx.drawImage(im,8+k.maxL-f.cx,k.H-8-f.h);k.ctx.globalAlpha=1;
}
function order(n){const o=[...Array(n).keys()];if(pp.checked)for(let i=n-2;i>0;i--)o.push(i);return o}
function tick(now){
  const step=+ms.value;
  for(const k of cards){
    const o=order(k.a.frames.length),pos=(now/step),idx=Math.floor(pos)%o.length,fr=pos-Math.floor(pos);
    k.ctx.clearRect(0,0,k.W,k.H);
    if(blend.checked){draw(k,o[idx],1);draw(k,o[(idx+1)%o.length],fr)}else draw(k,o[idx],1);
  }
  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);
</script></html>"""


def main():
    acts = collect()
    OUT.write_text(HTML.replace("__DATA__", json.dumps(acts, ensure_ascii=False)), encoding="utf-8")
    print(f"동작 {len(acts)}개 → {OUT}")


if __name__ == "__main__":
    main()
