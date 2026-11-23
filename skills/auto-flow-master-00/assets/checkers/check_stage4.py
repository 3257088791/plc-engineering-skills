#!/usr/bin/env python3
"""阶段4 静态门禁（项目无关，v2 收紧版）。

v1 的问题：把 SCL 局部量（#i/#code/#cand）与"数组赋值给符号"误判为违规，
噪音 109 条，门禁会被无视。v2 收紧为：

- 单一写入者：只看**全局符号**（带引号的 "NAME"），且要求出现在 **≥2 个不同文件** 才算违规
- NC 未取反：只在 **IF/ELSIF/WHILE 条件表达式内部**判定，且跳过 `:=` 赋值右侧
- 读写混用：只针对 HMI/模式/权限/显示 类命名，且降级为 WARN

规则编号仍与 skills 附录 Z 对应。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 输出统一 UTF-8，保证编排器/CI 按固定编码解析首行 PASS/FAIL
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DEFAULT_PROFILE = {
    "naming": {
        "fault": ["fault", "alarm", "error", "故障", "报警"],
        "latch": ["latch", "lock", "锁存", "自保"],
        "state": ["step", "seq", "code", "index", "idx", "count", "cycles", "no_",
                  "步序", "步号", "工步", "编号", "计数", "序号"],
        "hmi": ["hmi", "display", "disp", "screen", "画面", "显示"],
        "mode": ["mode", "auth", "permit", "enable", "level", "模式", "权限", "允许", "使能"],
        "business": ["full", "empty", "no_car", "nocar", "unpaid", "unauth",
                     "满", "无车", "空位", "未付", "未授权", "超限", "超长", "超宽"]
    },
    "skip": []
}

SCL_SECTION = re.compile(r"\b(VAR_INPUT|VAR_OUTPUT|VAR_IN_OUT|VAR_TEMP|VAR_STAT|VAR)\b(.*?)\bEND_VAR\b", re.S)
DECL = re.compile(
    r"^\s*([A-Za-z_\u4e00-\u9fa5][\w\u4e00-\u9fa5]*)\s*:\s*"
    r"(ARRAY\s*\[[^\]]+\]\s+OF\s+[A-Za-z_][\w.]*|[A-Za-z_][\w.]*)\s*(?::=\s*[^;]+)?;", re.M)
GLOBAL_ASSIGN = re.compile(r'"([^"]+)"\s*:=')
GLOBAL_USE = re.compile(r'"([^"]+)"')
COND_BLOCK = re.compile(r"\b(IF|ELSIF|WHILE)\b(.*?)\b(THEN|DO)\b", re.S | re.I)
DECL_BLOCK_TYPES = ["R_TRIG", "F_TRIG", "TON", "TOF", "TP", "CTU", "CTD", "CTUD"]


def load_profile(path: str | None) -> dict:
    prof = json.loads(json.dumps(DEFAULT_PROFILE))
    if path:
        user = json.loads(Path(path).read_text(encoding="utf-8"))
        for k, v in user.items():
            if isinstance(v, dict):
                prof.setdefault(k, {}).update(v)
            else:
                prof[k] = v
    return prof


def norm(name: str) -> str:
    return re.sub(r"\[[^\]]*\]", "", str(name)).strip('"').strip().lower()


def hit(name: str, keys: list[str]) -> bool:
    n = norm(name)
    return any(k.lower() in n for k in keys)


def read_scl(path: Path) -> str:
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def load_tag_map(project: Path) -> dict:
    tags = {}
    csv_p = project / "output" / "03-electrical" / "plc_tag_map.csv"
    if csv_p.is_file():
        import csv
        with csv_p.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                sym = (r.get("Symbol") or "").strip()
                if not sym:
                    continue
                tags[norm(sym)] = {
                    "symbol": sym, "address": (r.get("Address") or "").strip(),
                    "datatype": (r.get("DataType") or "").strip(),
                    "polarity": (r.get("NcSemantic") or "").strip(),
                    "io_id": (r.get("IO-ID") or "").strip()}
        return tags
    xlsx = project / "output" / "03-electrical" / "io_address.xlsx"
    if xlsx.is_file():
        try:
            from openpyxl import load_workbook
        except ImportError:
            return tags
        wb = load_workbook(xlsx, read_only=True, data_only=True)
        ws = wb.worksheets[0]
        head = [("" if c.value is None else str(c.value).strip()) for c in next(ws.iter_rows(min_row=1, max_row=1))]
        for row in ws.iter_rows(min_row=2, values_only=True):
            d = dict(zip(head, row))
            sym = str(d.get("设备标签") or "").strip()
            if sym:
                tags[norm(sym)] = {"symbol": sym, "address": str(d.get("物理地址") or ""),
                                   "datatype": "", "polarity": "", "io_id": str(d.get("IO-ID") or "")}
        wb.close()
    return tags


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--profile", default=None)
    ap.add_argument("--json", default=None)
    ap.add_argument("--skip", nargs="*", default=[])
    a = ap.parse_args()

    project = Path(a.project).expanduser().resolve()
    src_dir = project / "output" / "04-scl" / "src"
    if not src_dir.is_dir():
        print("FAIL")
        print(f" - 找不到 {src_dir}")
        return 2
    prof = load_profile(a.profile)
    skip = set(prof.get("skip") or []) | set(a.skip)
    N = prof["naming"]
    files = sorted(src_dir.glob("*.scl"))
    if not files:
        print("FAIL")
        print(f" - {src_dir} 下没有 .scl")
        return 2

    texts = {f.name: read_scl(f) for f in files}
    tags = load_tag_map(project)
    findings = []

    def add(rule, level, msg, file="", line=0):
        findings.append({"rule": rule, "level": level, "msg": msg, "file": file, "line": line})

    # ---------- 全局符号写入者（按文件去重） ----------
    writers: dict[str, dict[str, list[int]]] = {}
    for fname, text in texts.items():
        for m in GLOBAL_ASSIGN.finditer(text):
            key = norm(m.group(1))
            line = text[:m.start()].count("\n") + 1
            writers.setdefault(key, {}).setdefault(fname, []).append(line)

    # CHK-S4-01 同一全局符号被 ≥2 个块写入
    if "CHK-S4-01" not in skip:
        for key, per_file in sorted(writers.items()):
            if len(per_file) < 2:
                continue
            # 排除：跨文件但仅"一次性初值赋值"（同一行模式）无法区分，这里按规则报出
            where = "; ".join(f"{f}:{','.join(map(str, ls[:3]))}" for f, ls in list(per_file.items())[:4])
            add("CHK-S4-01", "FAIL",
                f"全局符号 {key} 被 {len(per_file)} 个块写入（{where}）：违反单一写入者，需指定唯一属主")

    # ---------- CHK-S4-03 条件内的 NC 点未取反 ----------
    if "CHK-S4-03" not in skip and tags:
        nc = {k: v for k, v in tags.items() if v["polarity"].upper().startswith("NC")}
        for fname, text in texts.items():
            for cm in COND_BLOCK.finditer(text):
                cond = cm.group(2)
                base = cm.start(2)
                for key, v in nc.items():
                    sym = v["symbol"]
                    for m in re.finditer(r'"' + re.escape(sym) + r'"', cond):
                        pre = cond[max(0, m.start() - 20):m.start()]
                        if re.search(r"\bNOT\b", pre, re.I):
                            continue
                        line = text[:base + m.start()].count("\n") + 1
                        add("CHK-S4-03", "FAIL",
                            f"常闭点 {sym}({v['address']}) 在条件中未取反（NC:TRUE=正常）：{fname}:{line}",
                            fname, line)

    # ---------- CHK-S4-02 HMI/模式/权限类读写混用（WARN） ----------
    if "CHK-S4-02" not in skip:
        read_cond: dict[str, list[tuple[str, int]]] = {}
        for fname, text in texts.items():
            for cm in COND_BLOCK.finditer(text):
                for m in GLOBAL_USE.finditer(cm.group(2)):
                    line = text[:cm.start(2) + m.start()].count("\n") + 1
                    read_cond.setdefault(norm(m.group(1)), []).append((fname, line))
        for key in sorted(set(writers) & set(read_cond)):
            if not (hit(key, N["hmi"]) or hit(key, N["mode"])):
                continue
            w = writers[key]; f0 = sorted(w)[0]
            r = read_cond[key][0]
            add("CHK-S4-02", "WARN",
                f"{key} 既被 {f0} 写入（:{w[f0][0]}）又被 {r[0]}:{r[1]} 当条件读取："
                f"请确认该点是 HMI 输入还是显示位，不得两用（S-04）",
                f0, w[f0][0])

    # ---------- CHK-S4-04 有锁存无上电屏蔽 ----------
    if "CHK-S4-04" not in skip:
        latch = [k for k in writers if hit(k, N["latch"])]
        has_fs = any(re.search(r"FirstScan|OB100|Startup|上电|PowerUp", t, re.I) for t in texts.values())
        if latch and not has_fs:
            add("CHK-S4-04", "WARN",
                f"存在锁存量（{', '.join(latch[:5])}）但无 FirstScan/OB100/上电屏蔽：首扫描输入全 0 可能被误判为动作（S-02）")

    # ---------- CHK-S4-05 声明为 Bool 的状态量 ----------
    if "CHK-S4-05" not in skip:
        for fname, text in texts.items():
            for sec in SCL_SECTION.finditer(text):
                if sec.group(1) == "VAR_TEMP" and "CHK-S4-07" not in skip:
                    for d in DECL.finditer(sec.group(2)):
                        if d.group(2).strip().upper() in DECL_BLOCK_TYPES:
                            line = text[:sec.start() + d.start()].count("\n") + 1
                            add("CHK-S4-07", "FAIL",
                                f"实例 {d.group(1)} 声明在 VAR_TEMP（必须静态化）", fname, line)
                for d in DECL.finditer(sec.group(2)):
                    if hit(d.group(1), N["state"]) and d.group(2).strip().lower() == "bool":
                        line = text[:sec.start() + d.start()].count("\n") + 1
                        add("CHK-S4-05", "FAIL",
                            f"状态/编码量 {d.group(1)} 声明为 Bool（应用 INT/DINT）", fname, line)

    # ---------- CHK-S4-06 变量表中为 Bool 的状态量 ----------
    if "CHK-S4-06" not in skip and tags:
        for key, v in tags.items():
            if hit(v["symbol"], N["state"]) and v["datatype"].lower() == "bool":
                add("CHK-S4-06", "FAIL",
                    f"变量表中 {v['symbol']}({v['address']}) 属状态/编码量但为 Bool：应用字类型（S-05）")

    # ---------- CHK-S4-08 业务信号与故障锁存共存（人工确认） ----------
    if "CHK-S4-08" not in skip:
        biz = sorted({k for k in writers if hit(k, N["business"])} |
                     {k for k in read_cond if hit(k, N["business"])})
        fault = [k for k in writers if hit(k, N["fault"]) or hit(k, N["latch"])]
        if biz and fault:
            add("CHK-S4-08", "WARN",
                f"业务类信号 {', '.join(biz[:6])} 与故障/锁存量 {', '.join(fault[:3])} 共存："
                f"请人工确认业务拒绝条件未进入故障锁存（S-01）")

    fails = [f for f in findings if f["level"] == "FAIL"]
    warns = [f for f in findings if f["level"] == "WARN"]
    verdict = "PASS" if not fails else "FAIL"
    print(verdict)  # 首行必须是 PASS/FAIL（编排器门禁契约）
    print(f"检查 {len(files)} 个 .scl | 极性点位 {len(tags)} | 全局符号 {len(writers)}")
    for f in fails:
        print(f"  [FAIL] {f['rule']}  {f['msg']}")
    for f in warns:
        print(f"  [WARN] {f['rule']}  {f['msg']}")
    verdict = "PASS" if not fails else "FAIL"
    print(f"\n结论: {verdict}  （FAIL {len(fails)} / WARN {len(warns)}）")
    if a.json:
        Path(a.json).write_text(json.dumps({"verdict": verdict, "findings": findings},
                                           ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())