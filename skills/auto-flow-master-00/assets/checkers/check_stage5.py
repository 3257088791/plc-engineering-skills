#!/usr/bin/env python3
"""阶段5 静态门禁（项目无关）：对 test_steps.csv / results.xlsx 做可执行性与执行覆盖检查。

设计原则
- 不写死项目内容：列名、算子、阈值全部可配置（--profile），默认为中英通用写法
- 点位合法性来自项目自有产物（io_address.xlsx / plc_tag_map.csv）
- 退出码 1 表示 FAIL

用法:
    python check_stage5.py --project D:\\proj
    python check_stage5.py --project D:\\proj --results output/05-sim-trace/results.xlsx
    python check_stage5.py --project D:\\proj --profile my_rules.json --json out.json

规则一览（编号与 skills 附录 Z 对应）
    CHK-S5-01  T-02  缺"前置态"列（模式/权限/初始化）              FAIL
    CHK-S5-02  T-02  缺"判定时刻"列或判定时刻早于保持时间           FAIL
    CHK-S5-03  T-04  激励/期望表达式不可解析或算子越界               FAIL
    CHK-S5-04  T-04  引用了项目点位表中不存在的点位                  FAIL
    CHK-S5-05  T-04  保持时间不可解析或低于下限                      FAIL
    CHK-S5-06  T-03  期望值为空或非整数                              FAIL
    CHK-S5-07  T-02  场景含"超时/未到位"但保持时间短于阈值           WARN
    CHK-S5-08  T-01  执行覆盖率=0（results 全为未执行）              FAIL
    CHK-S5-09  E-02  结果判定词不在白名单                            FAIL
"""
from __future__ import annotations

import argparse
import csv
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
    "columns": {
        "test_id": ["TEST-ID", "TEST_ID", "用例编号"],
        "scene": ["测试场景", "场景", "SCENE"],
        "stimulus": ["输入激励", "激励", "STIMULUS"],
        "hold": ["保持时间", "HOLD"],
        "expect": ["期望输出", "期望", "EXPECT"],
        "precondition": ["前置态", "前置条件", "初始状态", "INITIAL", "PRE"],
        "judge_at": ["判定时刻", "判定点", "采样时刻", "JUDGE"]
    },
    "operators": ["=", ">=", "<=", "==", "!=", ">", "<"],
    "limits": {"min_hold_ms": 500, "timeout_keywords": ["超时", "未到位", "timeout"]},
    "verdicts": ["通过", "失败", "未执行", "阻塞", "PASS", "FAIL", "SKIP", "BLOCKED"],
    "skip": []
}


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


def find_col(headers: list[str], keys: list[str]) -> str | None:
    for h in headers:
        hn = h.strip().upper()
        for k in keys:
            if k.upper() in hn:
                return h
    return None


def load_io_ids(project: Path) -> set[str]:
    out = set()
    csv_p = project / "output" / "03-electrical" / "plc_tag_map.csv"
    if csv_p.is_file():
        with csv_p.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                v = (r.get("IO-ID") or "").strip()
                if v:
                    out.add(v)
        if out:
            return out
    xlsx = project / "output" / "03-electrical" / "io_address.xlsx"
    if xlsx.is_file():
        try:
            from openpyxl import load_workbook
        except ImportError:
            return out
        wb = load_workbook(xlsx, read_only=True, data_only=True)
        ws = wb.worksheets[0]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row and row[0]:
                out.add(str(row[0]).strip())
        wb.close()
    return out


PAIR = re.compile(r"^\s*(IO-\d+)\s*(>=|<=|==|!=|=|>|<)\s*(-?\d+)\s*$")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--results", default=None)
    ap.add_argument("--profile", default=None)
    ap.add_argument("--json", default=None)
    ap.add_argument("--skip", nargs="*", default=[])
    a = ap.parse_args()

    project = Path(a.project).expanduser().resolve()
    steps = project / "output" / "05-sim-trace" / "test_steps.csv"
    if not steps.is_file():
        print("FAIL")
        print(f" - 找不到 {steps}")
        return 2
    prof = load_profile(a.profile)
    skip = set(prof.get("skip") or []) | set(a.skip)
    C = prof["columns"]; L = prof["limits"]
    io_ids = load_io_ids(project)

    with steps.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("FAIL")
        print(" - test_steps.csv 没有数据行")
        return 2
    headers = list(rows[0].keys())
    c_id = find_col(headers, C["test_id"]) or headers[0]
    c_scene = find_col(headers, C["scene"])
    c_stim = find_col(headers, C["stimulus"])
    c_hold = find_col(headers, C["hold"])
    c_exp = find_col(headers, C["expect"])
    c_pre = find_col(headers, C["precondition"])
    c_judge = find_col(headers, C["judge_at"])

    findings = []

    def add(rule, level, msg, test=""):
        findings.append({"rule": rule, "level": level, "msg": msg, "test": test})

    # CHK-S5-01 前置态列
    if "CHK-S5-01" not in skip and not c_pre:
        add("CHK-S5-01", "FAIL",
            f"缺少「前置态」列（模式/权限/初始化输入）。现有列: {headers}。"
            f"流程类用例没有前置态将无法驱动被测流程")
    elif c_pre and "CHK-S5-01" not in skip:
        empty = [r[c_id] for r in rows if not str(r.get(c_pre) or "").strip()]
        if empty:
            add("CHK-S5-01", "FAIL", f"{len(empty)} 条用例前置态为空：{empty[:8]}")

    # CHK-S5-02 判定时刻列
    if "CHK-S5-02" not in skip:
        if not c_judge:
            add("CHK-S5-02", "FAIL",
                "缺少「判定时刻」列：判定必须在保持时间之后（否则期望为 0 的用例会在 0ms 假通过）")
        else:
            for r in rows:
                try:
                    hold = int(str(r.get(c_hold) or "0").strip())
                    judge = int(str(r.get(c_judge) or "0").strip())
                except ValueError:
                    continue
                if judge < hold:
                    add("CHK-S5-02", "FAIL",
                        f"判定时刻 {judge}ms 早于保持时间 {hold}ms", r[c_id])

    # CHK-S5-03/04/06 表达式与点位
    for r in rows:
        tid = r[c_id]
        for col, label in ((c_stim, "激励"), (c_exp, "期望")):
            if not col:
                add("CHK-S5-03", "FAIL", f"缺少「{label}」列")
                continue
            raw = str(r.get(col) or "").strip()
            if not raw:
                add("CHK-S5-03", "FAIL", f"{label}为空", tid)
                continue
            for part in raw.split(";"):
                p = part.strip()
                if not p:
                    continue
                m = PAIR.match(p)
                if not m:
                    add("CHK-S5-03", "FAIL", f"{label}表达式不可解析: '{p}'", tid)
                    continue
                io = m.group(1)
                if "CHK-S5-04" not in skip and io_ids and io not in io_ids:
                    add("CHK-S5-04", "FAIL", f"{label}引用了点位表之外的 {io}", tid)
                if "CHK-S5-06" not in skip and label == "期望":
                    if not re.fullmatch(r"-?\d+", m.group(3)):
                        add("CHK-S5-06", "FAIL", f"期望值非整数: '{p}'", tid)

    # CHK-S5-05/07 保持时间
    for r in rows:
        tid = r[c_id]
        raw = str(r.get(c_hold) or "").strip() if c_hold else ""
        try:
            hold = int(raw)
        except ValueError:
            add("CHK-S5-05", "FAIL", f"保持时间不可解析: '{raw}'", tid)
            continue
        if hold < L["min_hold_ms"]:
            add("CHK-S5-05", "FAIL", f"保持时间 {hold}ms 低于下限 {L['min_hold_ms']}ms", tid)
        scene = str(r.get(c_scene) or "") if c_scene else ""
        if any(k in scene for k in L["timeout_keywords"]) and hold < L["min_hold_ms"] * 10:
            add("CHK-S5-07", "WARN",
                f"场景含超时语义但保持时间仅 {hold}ms，需确认是否覆盖超时阈值", tid)

    # CHK-S5-08/09 执行覆盖与判定词
    if a.results:
        rp = Path(a.results)
        if not rp.is_absolute():
            rp = project / a.results
        if rp.is_file():
            try:
                from openpyxl import load_workbook
                wb = load_workbook(rp, read_only=True, data_only=True)
                verdicts = []
                for ws in wb.worksheets:
                    head = [("" if c.value is None else str(c.value).strip())
                            for c in next(ws.iter_rows(min_row=1, max_row=1))]
                    if not any("判定" in h or "结果" in h.upper() for h in head):
                        continue
                    idx = next(i for i, h in enumerate(head) if "判定" in h or "结果" in h.upper())
                    for row in ws.iter_rows(min_row=2, values_only=True):
                        if row and row[idx]:
                            verdicts.append(str(row[idx]).strip())
                wb.close()
                if verdicts:
                    executed = [v for v in verdicts if v not in ("未执行", "SKIP", "阻塞", "BLOCKED")]
                    if "CHK-S5-08" not in skip and not executed:
                        add("CHK-S5-08", "FAIL",
                            f"执行覆盖率=0（{len(verdicts)} 条全为未执行/阻塞）：不得判阶段5 通过（G-02）")
                    bad = sorted({v for v in verdicts if v not in prof["verdicts"]})
                    if "CHK-S5-09" not in skip and bad:
                        add("CHK-S5-09", "FAIL", f"判定词越界: {bad}")
            except ImportError:
                add("CHK-S5-08", "WARN", "未安装 openpyxl，跳过结果文件检查")
        else:
            add("CHK-S5-08", "WARN", f"结果文件不存在: {rp}")

    fails = [f for f in findings if f["level"] == "FAIL"]
    warns = [f for f in findings if f["level"] == "WARN"]
    verdict = "PASS" if not fails else "FAIL"
    print(verdict)  # 首行必须是 PASS/FAIL（编排器门禁契约）
    print(f"用例数: {len(rows)} | 点数表: {len(io_ids)} | 列: 前置态={'有' if c_pre else '缺'} 判定时刻={'有' if c_judge else '缺'}")
    for f in fails:
        print(f"  [FAIL] {f['rule']}  {f['test'] + ' ' if f['test'] else ''}{f['msg']}")
    for f in warns:
        print(f"  [WARN] {f['rule']}  {f['test'] + ' ' if f['test'] else ''}{f['msg']}")
    verdict = "PASS" if not fails else "FAIL"
    print(f"\n结论: {verdict}  （FAIL {len(fails)} / WARN {len(warns)}）")
    if a.json:
        Path(a.json).write_text(json.dumps({"verdict": verdict, "findings": findings},
                                           ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())