# ./output/06-eval-archive/_work/validate_stage6.py
import hashlib
import sys
import json
import re
from pathlib import Path

from openpyxl import load_workbook

OUT = Path("./output")
# 输出统一 UTF-8，保证编排器/CI 按固定编码解析首行 PASS/FAIL
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ERR = []


def check(cond, msg):
    if not cond:
        ERR.append(msg)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    for name in ("project_evaluation_report.md", "quality_metrics_summary.xlsx",
                 "project_archive_list.md"):
        p = OUT / "06-eval-archive" / name
        check(p.exists() and p.stat().st_size > 0, f"缺少输出：{name}")

    data = json.loads((OUT / "06-eval-archive" / "_work" / "eval_data.json").read_text(encoding="utf-8"))
    payload = {k: v for k, v in data.items() if k != "fingerprint"}
    fp = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    check(fp == data.get("fingerprint"), "eval_data 指纹不匹配（生成后被改过）")

    report = (OUT / "06-eval-archive" / "project_evaluation_report.md").read_text(encoding="utf-8")
    check(f"数据指纹：{fp[:16]}" in report, "报告缺少数据指纹或指纹不一致")
    check(not re.search(r"验收通过|项目合格|安全合规", report), "报告出现越权结论")

    wb = load_workbook(OUT / "06-eval-archive" / "quality_metrics_summary.xlsx", data_only=True)
    for s in ("00-说明", "01-指标台账", "02-工时成本", "03-风险清单", "04-归档核对"):
        check(s in wb.sheetnames, f"缺少工作表：{s}")
    ws = wb["01-指标台账"]
    rows = [[c.value for c in r] for r in ws.iter_rows(min_row=2) if r[0].value]
    ids = {r[0] for r in rows}
    check(len(rows) == 14 and ids == {f"M-{i:02d}" for i in range(1, 15)}, "指标台账行数/ID不符")
    check(all(r[7] in ("已计算", "部分", "待统计", "未开展", "未执行", "不适用") for r in rows),
          "指标状态词非法")

    archive = (OUT / "06-eval-archive" / "project_archive_list.md").read_text(encoding="utf-8")
    for item in data["archive"]["items"]:
        check(item["path"] in archive, f"归档清单缺条目：{item['path']}")

    now = {k: sha(Path(k)) for k in data["inputs"] if Path(k).exists()}
    check(now == data["inputs"], "上游文件哈希变化：本技能不得修改上游")

    missing = [r for r in rows if r[7] == "待统计"]
    check(f"待统计 {len(missing)} 项" in report, "报告缺少逐字样「待统计 N 项」或与台账不一致")

    print("PASS" if not ERR else "FAIL")
    for e in ERR:
        print(" -", e)


if __name__ == "__main__":
    import sys
    try:
        main()
    except Exception as e:  # 输入不可解析按 2 处理，不得静默通过
        print("FAIL")
        print(f" - 校验异常：{type(e).__name__}: {e}")
        sys.exit(2)
    print("PASS" if not ERR else "FAIL")
    for e in ERR:
        print(" -", e)
    sys.exit(0 if not ERR else 1)