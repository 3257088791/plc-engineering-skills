#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仓库级一致性自检（只读）。

用途：每次改完技能，跑一遍，确认没有把契约改断。
覆盖：frontmatter / 代码围栏 / 编码、分阶段输出布局、跨技能列契约、
      校验脚本可编译、脚本内路径、assets 哈希。

用法：
    python tools/ci_verify.py [--skills <技能根目录>] [--json out.json]

退出码：0 = 全部通过，1 = 有失败项，2 = 路径/依赖问题。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SKILL_DIRS = {
    "00": "auto-flow-master-00",
    "01": "req-spec-01",
    "02": "scheme-io-bom-02",
    "03": "elec-construction-03",
    "04": "plc-scl-gen-04",
    "05": "sim-trace-05",
    "06": "eval-archive-06",
}

STAGE_DIRS = {
    "00": "00-flow",
    "01": "01-requirements",
    "02": "02-scheme-io-bom",
    "03": "03-electrical",
    "04": "04-scl",
    "05": "05-sim-trace",
    "06": "06-eval-archive",
}

CSV_HDR_8 = (
    "TEST-ID,关联REQ-ID,测试场景,输入激励,前置态,保持时间(ms),判定时刻,期望输出"
)
IO_ADDR_COLS = (
    "IO-ID | 信号名 | PLC符号 | 类型 | 物理地址 | 方向 | 地址区 | 字节位 | "
    "设备标签 | 备用标志 | NC语义 | 关联REQ-ID | 回路号 | 关联BOM-ID | 地址版本 | 备注"
)
TERM_COLS = (
    "TERM-ID | 端子排 | 端子号 | 线号 | IO-ID | 回路号 | 信号名称 | 导线截面 | 颜色 | 对接端子"
)

# v1.x 平铺路径：阶段1~6 的正文里不应再出现
FLAT_PATH = re.compile(
    r"output/(?:requirements_spec|clarification_shturl|scheme\.md|io_list\.xlsx|"
    r"bom\.xlsx|multi_check_report|io_address\.xlsx|loop_description|cable_schedule|"
    r"terminal_list|clause_check|drawing_data|plc_tag_map|compilation_fix_shturl|"
    r"test_steps|results\.xlsx|traceability_matrix|project_evaluation_report|"
    r"quality_metrics_summary|project_archive_list)"
)

ASSETS = [
    ("auto-flow-master-00/assets/checkers", ["check_stage4.py", "check_stage5.py"]),
    ("sim-trace-05/assets", ["validate_stage5.py"]),
    ("eval-archive-06/assets",
     ["stage6_collect.py", "stage6_render.py", "validate_stage6.py"]),
]

results: list[tuple[str, bool, str]] = []


def ck(name: str, cond: bool, detail: str = "") -> None:
    results.append((name, bool(cond), detail))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills", default=None,
                    help="技能根目录，默认 <仓库根>/skills")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    root = Path(a.skills) if a.skills else Path(__file__).resolve().parent.parent / "skills"
    if not root.is_dir():
        print(f"FAIL\n - 技能目录不存在：{root}")
        return 2

    paths = {k: root / v / "SKILL.md" for k, v in SKILL_DIRS.items()}
    missing = [str(p) for p in paths.values() if not p.is_file()]
    if missing:
        print("FAIL")
        for m in missing:
            print(f" - 缺少 SKILL.md：{m}")
        return 2

    T = {}
    for k, p in paths.items():
        raw = p.read_bytes()
        T[k] = raw.decode("utf-8")
        ck(f"[{k}] 无 BOM", not raw.startswith(b"\xef\xbb\xbf"))
        ck(f"[{k}] 无 CRLF 混用", b"\r\n" not in raw)

    # ---------- A. 结构完整性 ----------
    for k, p in paths.items():
        t = T[k]
        fm = re.match(r"^---\n(.*?)\n---", t, re.S)
        head = "\n" + (fm.group(1) if fm else "")
        ck(f"[{k}] frontmatter 合法", bool(fm) and "\nname:" in head and "\ndescription:" in head)
        fences = len(re.findall(r"(?m)^```", t))
        ck(f"[{k}] 代码围栏成对", fences % 2 == 0, f"{fences} 个")
        ck(f"[{k}] 行数合理", len(t.splitlines()) > 200, f"{len(t.splitlines())} 行")

    # ---------- B. 分阶段输出布局 ----------
    t00 = T["00"]
    ck("[00] layout_version 固定 2.0", '"layout_version": "2.0"' in t00)
    ck("[00] output_layout=staged", '"output_layout": "staged"' in t00)
    ck("[00] stage_dirs 已声明", '"stage_dirs"' in t00)
    ck("[00] 状态文件位于 00-flow",
       "output/00-flow/flow_status.json" in t00)
    for k in ("00", "01", "02", "03", "04", "05", "06"):
        ck(f"[00] 契约含 {STAGE_DIRS[k]}/", f"{STAGE_DIRS[k]}/" in t00)
    for code in ("E00_LAYOUT_INVALID", "E00_LAYOUT_CONFLICT",
                 "E00_LAYOUT_VERSION", "E00_PATH_UNSAFE"):
        ck(f"[00] 布局错误码 {code}", code in t00)

    for k in ("01", "02", "03", "04", "05", "06"):
        ck(f"[{k}] 输出在本阶段目录 {STAGE_DIRS[k]}/",
           f"output/{STAGE_DIRS[k]}/" in T[k])
        hits = sorted(set(FLAT_PATH.findall(T[k])))
        ck(f"[{k}] 无旧平铺 output/ 路径", not hits, "、".join(hits))

    # ---------- C. 00 流程契约 ----------
    ck("[00] completion_scope 含 +logic_unverified", "+logic_unverified" in t00)
    ck("[00] stages 枚举含 deviation", "`deviation`" in t00)
    ck("[00] G5-02 CSV 8 列表头", CSV_HDR_8 in t00)
    ck("[00] 变量表工具入契约", "ImportPlcTagTable" in t00)
    ck("[00] capabilities.json 入契约", "capabilities.json" in t00)
    ck("[00] G5-07 要求退出码 0", "退出码为 `0` 才通过" in t00)
    ck("[00] G5-07 从 sim-trace-05 复制校验器",
       "sim-trace-05/assets/validate_stage5.py" in t00)
    ck("[00] 阶段3 门禁含 plc_tag_map", "plc_tag_map.csv` 存在且行数" in t00)
    ck("[00] 错误码总数 69",
       len(set(re.findall(r"E\d{2}_[A-Z0-9_]+", t00))) == 69,
       f"{len(set(re.findall(r'E[0-9]{{2}}_[A-Z0-9_]+', t00)))} 个")

    # ---------- D. 01 / 02 ----------
    t01 = T["01"]
    ck("[01] 默认模式为 true", "未说明按 `true`" in t01)
    ck("[01] 无旧默认 false 表述", "按 `false`，提问并等待 |" not in t01)
    ck("[01] REQ-ID 正则未退化", r"REQ-(\d+)" not in t01)

    t02 = T["02"]
    ck("[02] 无 REQ-SAF 示例", "REQ-SAF" not in t02)
    ck("[02] 极性落位规则", "`24VDC/NC`" in t02)
    ck("[02] 前置类落位规则", "`[PRE]`" in t02)

    # ---------- E. 03 电气设计 ----------
    t03 = T["03"]
    ck("[03] io_address 16 列", IO_ADDR_COLS in t03)
    ck("[03] terminal_list 10 列", TERM_COLS in t03)
    ck("[03] 提供 plc_tag_table.xml", "plc_tag_table.xml" in t03)
    ck("[03] plc_tag_map 章节", "plc_tag_map.csv" in t03)
    ck("[03] 已有附录 Z", "## 附录 Z：实机回归失败模式与强制检查" in t03)

    # ---------- F. 04 SCL ----------
    t04 = T["04"]
    ck("[04] 源码位于 04-scl/src", "output/04-scl/src" in t04)
    ck("[04] 变量表用 ImportPlcTagTable", "ImportPlcTagTable" in t04)
    ck("[04] 使用说明为推荐交付物", "使用说明" in t04)
    ck("[04] 冒烟移交阶段5", "冒烟移交阶段5" in t04)
    ck("[04] 4.4 在 4.5 之前", t04.index("### 4.4") < t04.index("### 4.5"))

    # ---------- G. 05 仿真与追溯 ----------
    t05 = T["05"]
    ck("[05] CSV 8 列定义", CSV_HDR_8 in t05)
    ck("[05] 校验器外置引用", "assets/validate_stage5.py" in t05)
    ck("[05] 冒烟小节存在", "冒烟优先" in t05)
    ck("[05] 前置态列为硬性", "`前置态`" in t05)
    ck("[05] 过程证据在 _work", "_work" in t05)

    # ---------- H. 06 评估 ----------
    t06 = T["06"]
    ck("[06] M-11 名为综合追溯覆盖率", "综合追溯覆盖率" in t06)
    ck("[06] 工时系数须有来源", "模型耗时 × k" in t06)
    ck("[06] M-12 标注占位", "占位指标" in t06)
    ck("[06] 17 项交付物口径", "17 项" in t06)

    # ---------- I. 校验脚本 ----------
    for rel, files in ASSETS:
        for name in files:
            p = root / rel / name
            exists = p.is_file()
            ck(f"[脚本] {name} 存在", exists)
            if not exists:
                continue
            try:
                compile(p.read_text(encoding="utf-8"), str(p), "exec")
                okc, detail = True, ""
            except SyntaxError as e:
                okc, detail = False, f"{e.lineno}: {e.msg}"
            ck(f"[脚本] {name} 可编译", okc, detail)

    s4 = (root / "auto-flow-master-00/assets/checkers/check_stage4.py").read_text(encoding="utf-8")
    s5 = (root / "auto-flow-master-00/assets/checkers/check_stage5.py").read_text(encoding="utf-8")
    v5 = (root / "sim-trace-05/assets/validate_stage5.py").read_text(encoding="utf-8")
    v6 = (root / "eval-archive-06/assets/validate_stage6.py").read_text(encoding="utf-8")
    c6 = (root / "eval-archive-06/assets/stage6_collect.py").read_text(encoding="utf-8")

    ck("[脚本] check_stage4 读 03-electrical", '"03-electrical"' in s4)
    ck("[脚本] check_stage4 读 04-scl/src", '"04-scl"' in s4 and '"src"' in s4)
    ck("[脚本] check_stage5 读 05-sim-trace", '"05-sim-trace"' in s5)
    ck("[脚本] validate_stage5 读 01-requirements", '"01-requirements"' in v5)
    ck("[脚本] validate_stage5 读 05-sim-trace", '"05-sim-trace"' in v5)
    ck("[脚本] validate_stage5 首行 PASS/FAIL",
       'print("PASS" if not ERR else "FAIL")' in v5)
    ck("[脚本] validate_stage5 有退出码", "sys.exit(0 if not ERR else 1)" in v5)
    ck("[脚本] validate_stage5 允许部分链路", 'all(m[7] == "完整"' not in v5)
    ck("[脚本] validate_stage6 读 06-eval-archive", '"06-eval-archive"' in v6)
    ck("[脚本] stage6_collect 输入全部带阶段目录",
       c6.count('"output/0') >= 17, f"{c6.count(chr(34) + 'output/0')} 处")
    ck("[脚本] 无平铺结果路径",
       not re.search(r'OUT\s*/\s*"(?:test_steps\.csv|results\.xlsx|traceability_matrix\.xlsx)"',
                     v5 + v6))

    # ---------- J. assets 哈希 ----------
    for rel, files in ASSETS:
        d = root / rel
        sums: dict[str, str] = {}
        f = d / "SHA256SUMS.txt"
        if f.is_file():
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    parts = line.split()
                    if len(parts) == 2:
                        sums[parts[1]] = parts[0]
        for name in files:
            p = d / name
            if not p.is_file():
                continue
            actual = hashlib.sha256(p.read_bytes()).hexdigest()
            ok = sums.get(name) == actual
            ck(f"[SHA] {name} 哈希匹配", ok,
               "" if ok else ("未登记" if name not in sums else "哈希不一致，请运行 tools/regen_sha.py"))

    failed = [r for r in results if not r[1]]
    if a.json:
        Path(a.json).write_text(
            json.dumps({"total": len(results),
                        "failed": [{"check": n, "detail": d} for n, ok, d in results if not ok]},
                       ensure_ascii=False, indent=2),
            encoding="utf-8")
    return 0 if not failed else 1


if __name__ == "__main__":
    code = main()
    print("PASS" if code == 0 else "FAIL")
    for name, ok, detail in results:
        if not ok:
            print(f" - {name}" + (f" [{detail}]" if detail else ""))
    print(f"合计 {len(results)} 项，失败 {sum(1 for _, ok, _ in results if not ok)} 项",
          file=sys.stderr)
    sys.exit(code)