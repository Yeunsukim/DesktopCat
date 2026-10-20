"""실행 파일의 디지털 서명 확인 (Authenticode).

서명이 '유효'하면 만든 곳이 확인된 프로그램이라는 뜻이라 수상도가 크게 내려간다 (서명 없음 = 악성이라는 뜻은 아니다).
PowerShell 의 Get-AuthenticodeSignature 를 한 번에 여러 파일로 불러서 쓰고(시작 비용을 한 번만 낸다), 결과는 (경로·수정시각·크기) 기준으로 보관해서
같은 파일은 다시 확인하지 않는다. 보조 프로세스(nethelper) 안에서만 부른다.

상태: Valid(유효) / NotSigned(서명 없음) / HashMismatch(서명 뒤에 파일이 바뀜 = 위험) / NotTrusted·UnknownError·Error(확인 못 함) / ...
"""
import json
import os
import subprocess
from pathlib import Path

PS_SCRIPT = r"""
param($InFile, $OutFile)
$paths = Get-Content -Raw -Encoding UTF8 $InFile | ConvertFrom-Json
$out = @{}
foreach ($p in $paths) {
    try {
        $s = Get-AuthenticodeSignature -LiteralPath $p -ErrorAction Stop
        $subj = ''
        if ($s.SignerCertificate) { $subj = [string]$s.SignerCertificate.Subject }
        $out[$p] = @{ status = [string]$s.Status; subject = $subj }
    } catch {
        $out[$p] = @{ status = 'Error'; subject = '' }
    }
}
$out | ConvertTo-Json -Compress | Out-File -Encoding UTF8 $OutFile
"""
CREATE_NO_WINDOW = 0x08000000


def _publisher(subject: str) -> str:
    for part in subject.split(","):
        part = part.strip()
        if part.upper().startswith("CN="):
            return part[3:].strip('" ')
    return subject[:60]


def _key(path: str) -> str:
    try:
        st = os.stat(path)
        return "%s|%d|%d" % (path.lower(), int(st.st_mtime), st.st_size)
    except OSError:
        return path.lower() + "|?"


def _run_ps(paths, work_dir: Path, timeout=120):
    """PowerShell 로 서명을 한꺼번에 확인한다. {경로: {status, subject}}"""
    work_dir.mkdir(parents=True, exist_ok=True)
    inp, outp, ps = work_dir / "_sig_in.json", work_dir / "_sig_out.json", work_dir / "_sig.ps1"
    inp.write_text(json.dumps(list(paths), ensure_ascii=False), encoding="utf-8")
    ps.write_text(PS_SCRIPT, encoding="utf-8")
    if outp.exists():
        outp.unlink()
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(ps), "-InFile", str(inp), "-OutFile", str(outp)],
                   capture_output=True, timeout=timeout, creationflags=CREATE_NO_WINDOW)
    try:
        return json.loads(outp.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def check_many(paths, work_dir, runner=_run_ps):
    """{경로: {"status", "publisher"}}. 보관된 결과가 있으면 재사용한다. runner 는 시험에서 바꿔 끼운다."""
    work_dir = Path(work_dir)
    cache_file = work_dir / "sigcache.json"
    try:
        cache = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    out, todo = {}, []
    for p in dict.fromkeys(paths):
        if not p or not os.path.isfile(p):
            continue
        k = _key(p)
        if k in cache:
            out[p] = cache[k]
        else:
            todo.append(p)
    for i in range(0, len(todo), 60):
        chunk = todo[i:i + 60]
        try:
            res = runner(chunk, work_dir)
        except Exception:
            res = {}
        for p in chunk:
            r = res.get(p) or {"status": "Error", "subject": ""}
            val = {"status": r.get("status", "Error"), "publisher": _publisher(r.get("subject", ""))}
            out[p] = val
            if val["status"] != "Error":                    # 확인에 실패한 것은 보관하지 않고 다음에 다시 해 본다
                cache[_key(p)] = val
    if todo:
        if len(cache) > 5000:
            cache = dict(list(cache.items())[-3000:])
        try:
            cache_file.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    return out
