#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段 5 门禁的夹具测试（双向验证）。

正向：合格数据 → 校验器首行 PASS、退出码 0
反向：判定时刻早于保持时间 / 缺口行无依据 / 阶段6 缺输入 → 首行 FAIL、退出码 1 或 2

用法：python tools/smoke_stage5.py
退出码：0 = 全部符合预期，1 = 有不符合预期的行为，2 = 依赖缺失。
"""
from __future__ import annotations

import csv
import shutil
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    from openpyxl import Workbook
except ImportError:
    print("FAIL")
    print(" - 缺少依赖 openpyxl，请先 pip install openpyxl")
    sys.exit(2)

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / "skills"
PROJ = REPO / "samples" / "minimal_project"
OUT = PROJ / "output"

HDR = ["TEST-ID", "关联REQ-ID", "测试场景", "输入激励", "前置态",
       "保持时间(ms)", "判定时刻", "期望输出"]
ROWS = [
    ["TEST-001-01", "REQ-001", "正常工况:启动运行", "IO-001=1", "IO-021=1", "1000", "1200", "IO-010=1"],
    ["TEST-002-01", "REQ-002", "急停工况:运行中急停", "IO-021=0", "IO-001=1", "1000", "1200", "IO-010=0"],
    ["TEST-002-02", "REQ-002", "故障工况:输出断线", "IO-020=0", "IO-021=1", "1000", "1200", "IO-020=0"],
    ["TEST-002-03", "REQ-002", "复位异常工况:复位顺序反", "IO-021=1", "IO-001=0", "1000", "1200", "IO-010=0"],
]


def build_fixture() -> None:
    if PROJ.exists():
        shutil.rmtree(PROJ)
    OUT.mkdir(parents=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "需求表"
    ws.append(["REQ-ID", "需求内容", "验收准则", "优先级", "关联IO占位", "状态"])
    ws.append(["REQ-001", "启动后电机运行", "IO-010=1 且保持 1s", "高", "IO-010", "已确认"])
    ws.append(["REQ-002", "急停切断输出", "IO-010=0 且 IO-020=0", "高", "IO-020", "已确认"])
    wb.save(OUT / "requirements_spec.xlsx")

    (OUT / "plc_tag_map.csv").write_text(
        "IO-ID,Symbol,Address,DataType,Direction,NcSemantic,REQ-ID\n"
        "IO-001,SB1_START,I0.0,Bool,DI,NO,REQ-001\n"
        "IO-010,KM1_RUN,Q0.0,Bool,DO,NO,REQ-001\n"
        "IO-020,Y1_ESTOP,Q0.1,Bool,DO,NO,REQ-002\n"
        "IO-021,SB2_ESTOP_NC,I0.1,Bool,DI,NC,REQ-002\n",
        encoding="utf-8-sig",
    )

    write_csv(ROWS)

    wb = Workbook()
    w0 = wb.active
    w0.title = "00-说明"
    w0["A1"], w0["B1"] = "批次号", "SIM-20261116-01"
    w0["A2"], w0["B2"] = "通道", "PLCSIM_ADV"
    w0["A3"], w0["B3"] = "通过率分母口径", "通过数/已执行数"
    w1 = wb.create_sheet("01-测试结果")
    w1.append(["TEST-ID", "关联REQ-ID", "测试场景", "输入激励", "期望输出",
               "实际输出", "判定结果", "备注"])
    for r in ROWS:
        w1.append([r[0], r[1], r[2], r[3], r[7], r[7], "通过", "冒烟"])
    w2 = wb.create_sheet("02-问题定位")
    w2.append(["问题编号", "TEST-ID", "归属阶段", "证据", "建议"])
    wb.save(OUT / "results.xlsx")

    write_matrix(full=True)


def write_csv(rows) -> None:
    with (OUT / "test_steps.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\r\n")
        w.writerow(HDR)
        w.writerows(rows)


def write_matrix(full: bool) -> None:
    wb = Workbook()
    w0 = wb.active
    w0.title = "00-说明"
    w0["A1"], w0["B1"] = "需求测试覆盖率", 1.0
    w0["A2"], w0["B2"] = "链路完整率", 1.0
    w0["A3"], w0["B3"] = "结果覆盖率", 1.0
    w1 = wb.create_sheet("01-追溯矩阵")
    w1.append(["TRACE-ID", "REQ-ID", "IO-ID", "BOM-ID", "TERM-ID", "CODE-ID",
               "TEST-ID", "链路完整性", "备注"])
    if full:
        w1.append(["TRC-001-01", "REQ-001", "IO-010", "BOM-002", "X3-01", "FB_CONV",
                   "TEST-001-01", "完整", "显式关联"])
        w1.append(["TRC-002-01", "REQ-002", "IO-020", "BOM-003", "X4-01", "FB_STOP",
                   "TEST-002-01", "完整", "显式关联"])
    else:
        # 缺口行：标"部分"但备注为空 → 必须被判 FAIL
        w1.append(["TRC-001-01", "REQ-001", "IO-010", "BOM-002", "X3-01", "FB_CONV",
                   "TEST-001-01", "部分", ""])
    w2 = wb.create_sheet("02-反向索引")
    w2.append(["ID", "类型", "引用位置"])
    wb.save(OUT / "traceability_matrix.xlsx")


def run(name: str, script: Path, expect_first: str, expect_codes: tuple[int, ...],
        args: list[str] | None = None) -> bool:
    cmd = [sys.executable, str(script)] + (args or [])
    r = subprocess.run(cmd, capture_output=True, cwd=str(PROJ))
    out = (r.stdout or b"").decode("utf-8", errors="replace")
    lines = out.splitlines()
    first = lines[0] if lines else "<empty>"
    ok = (first == expect_first) and (r.returncode in expect_codes)
    print(f"{'PASS' if ok else 'FAIL'}  {name}: first={first} exit={r.returncode}"
          f"  期望 {expect_first}/{expect_codes}")
    if not ok:
        for ln in lines[:6]:
            print("      ", ln)
        err = (r.stderr or b"").decode("utf-8", errors="replace")[:400]
        if err:
            print("      stderr:", err.replace("\n", " ")[:300])
    return ok


def main() -> int:
    build_fixture()

    val5 = SKILLS / "sim-trace-05" / "assets" / "validate_stage5.py"
    chk5 = SKILLS / "auto-flow-master-00" / "assets" / "checkers" / "check_stage5.py"
    val6 = SKILLS / "eval-archive-06" / "assets" / "validate_stage6.py"

    for p in (val5, chk5, val6):
        if not p.is_file():
            print(f"FAIL\n - 缺少校验脚本：{p}")
            return 2

    ok = True
    ok &= run("validate_stage5 合格数据", val5, "PASS", (0,), ["--project", str(PROJ)])
    ok &= run("check_stage5 合格数据", chk5, "PASS", (0,),
              ["--project", str(PROJ), "--results", "output/results.xlsx"])
    ok &= run("validate_stage6 缺输入", val6, "FAIL", (1, 2))

    # 反向 1：判定时刻早于保持时间
    bad = [r[:] for r in ROWS]
    bad[0][6] = "500"
    write_csv(bad)
    ok &= run("validate_stage5 判定时刻过早", val5, "FAIL", (1,), ["--project", str(PROJ)])
    ok &= run("check_stage5 判定时刻过早", chk5, "FAIL", (1,),
              ["--project", str(PROJ), "--results", "output/results.xlsx"])
    write_csv(ROWS)

    # 反向 2：缺口行无依据
    write_matrix(full=False)
    ok &= run("validate_stage5 缺口行无依据", val5, "FAIL", (1,), ["--project", str(PROJ)])
    write_matrix(full=True)

    # 还原干净夹具
    build_fixture()
    print(f"\n夹具目录：{PROJ}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())