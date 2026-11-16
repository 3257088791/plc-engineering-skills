# ./output/_stage5/validate_stage5.py  —— 只读校验，不改任何文件
# 契约（与 auto-flow-master-00 §12.3 G5-07 一致）：
#   首行输出 PASS / FAIL；明细以 " - " 开头逐条输出；退出码 0=PASS，1=FAIL，2=输入缺失/不可解析。
# 用法：python validate_stage5.py [--project <项目根>]
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

try:
    from openpyxl import load_workbook
except ImportError:  # 缺依赖时按"输入缺失"处理，不得静默 PASS
    print("FAIL")
    print(" - 缺少依赖 openpyxl，无法校验 results.xlsx / traceability_matrix.xlsx")
    sys.exit(2)

CSV_HDR = ["TEST-ID", "关联REQ-ID", "测试场景", "输入激励", "前置态",
           "保持时间(ms)", "判定时刻", "期望输出"]
RES_HDR = ["TEST-ID", "关联REQ-ID", "测试场景", "输入激励", "期望输出",
           "实际输出", "判定结果", "备注"]
MAT_HDR = ["TRACE-ID", "REQ-ID", "IO-ID", "BOM-ID", "TERM-ID", "CODE-ID",
           "TEST-ID", "链路完整性", "备注"]
SCENES = ("正常工况", "急停工况", "故障工况", "复位异常工况")
# 输出统一 UTF-8，保证编排器/CI 按固定编码解析首行 PASS/FAIL
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ERR = []


def check(cond, msg):
    if not cond:
        ERR.append(msg)


def load_reqs(out):
    wb = load_workbook(out / "requirements_spec.xlsx", data_only=True)
    for ws in wb.worksheets:
        hdr = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
        if hdr[:1] == ["REQ-ID"]:
            return [dict(zip(hdr, ["" if v is None else str(v).strip() for v in r]))
                    for r in ws.iter_rows(min_row=2, values_only=True) if r and r[0]]
    raise SystemExit("【缺少输入：requirements_spec.xlsx 未找到六字段需求表】")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    out = Path(a.project).expanduser().resolve() / "output"

    for name in ("test_steps.csv", "results.xlsx", "traceability_matrix.xlsx"):
        check((out / name).is_file(), f"缺少输出：{name}")
    if ERR:
        return

    with (out / "test_steps.csv").open(encoding="utf-8-sig", newline="") as f:
        steps = list(csv.DictReader(f))
    check(bool(steps), "test_steps.csv 没有数据行")
    if not steps:
        return
    check(list(steps[0].keys()) == CSV_HDR, f"CSV 表头不符，应为 8 列：{CSV_HDR}")

    # T-02 前置态 / 判定时刻
    for s in steps:
        check(bool(str(s.get("前置态") or "").strip()),
              f"{s.get('TEST-ID')} 前置态为空（T-02）")
        try:
            hold = int(str(s.get("保持时间(ms)")).strip())
            judge = int(str(s.get("判定时刻")).strip())
        except (TypeError, ValueError):
            check(False, f"{s.get('TEST-ID')} 保持时间/判定时刻不是整数（T-02）")
            continue
        check(judge >= hold,
              f"{s.get('TEST-ID')} 判定时刻 {judge}ms 早于保持时间 {hold}ms（T-02）")

    wb_r = load_workbook(out / "results.xlsx", data_only=True)
    ws = wb_r["01-测试结果"]
    res = [[c.value for c in r] for r in ws.iter_rows(min_row=2) if r[0].value]
    check([c.value for c in ws[1]] == RES_HDR, "results 主表表头不符")
    check(len(res) == len(steps), "results 行数与 CSV 不一致")
    check({r[0] for r in res} == {s["TEST-ID"] for s in steps}, "TEST-ID 集合不一致")
    check(all(r[6] in ("通过", "失败", "未执行", "阻塞") for r in res), "判定词非法")
    check(all(r[:5] == [s["TEST-ID"], s["关联REQ-ID"], s["测试场景"],
                        s["输入激励"], s["期望输出"]]
              for r, s in zip(res, steps)), "结果表与 CSV 对应列不一致（按列名比对）")

    wb_m = load_workbook(out / "traceability_matrix.xlsx", data_only=True)
    wm = wb_m["01-追溯矩阵"]
    mat = [[c.value for c in r] for r in wm.iter_rows(min_row=2) if r[0].value]
    check([c.value for c in wm[1]] == MAT_HDR, "矩阵表头不符")
    check(len({m[0] for m in mat}) == len(mat), "TRACE-ID 重复")
    check(all(m[7] in ("完整", "部分") for m in mat), "链路完整性取值非法")
    # 缺口行允许存在，但必须写明依据（不得删行粉饰，也不得留空）
    gaps = [m for m in mat if m[7] == "部分"]
    check(all(str(m[8] or "").strip() for m in gaps),
          "链路完整性=部分 的行必须在备注列写明缺口依据（N/A 原因或别名说明）")

    reqs = load_reqs(out)
    ids = {r["REQ-ID"] for r in reqs if r.get("状态") in ("已确认", "【模拟回答】")}
    check(ids <= {m[1] for m in mat}, "矩阵未覆盖全部需求")
    for req in ids:
        check(any(s["关联REQ-ID"] == req for s in steps), f"{req} 无用例")

    note = " ".join(str(c.value) for row in wb_r["00-说明"].iter_rows()
                    for c in row if c.value is not None)
    scenes = Counter(s["测试场景"].split(":")[0] for s in steps)
    for sc in SCENES:
        check(scenes[sc] > 0 or f"不适用：{sc}" in note,
              f"场景未覆盖且 00-说明 未写「不适用：{sc}」及依据")

    fails = [r for r in res if r[6] == "失败"]
    dids = {row[1].value for row in wb_r["02-问题定位"].iter_rows(min_row=2) if row[1].value}
    check({r[0] for r in fails} <= dids, "失败项缺少问题定位行")

    executed = [r for r in res if r[6] in ("通过", "失败")]
    check(len(executed) >= 1 or "【仿真未执行：" in str(res[0][7] if res else ""),
          "执行覆盖率为 0 且未写「【仿真未执行：原因】」")


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        print("FAIL")
        print(f" - {e}")
        sys.exit(2)
    except Exception as e:  # 输入不可解析
        print("FAIL")
        print(f" - 校验异常：{type(e).__name__}: {e}")
        sys.exit(2)
    print("PASS" if not ERR else "FAIL")
    for e in ERR:
        print(" -", e)
    sys.exit(0 if not ERR else 1)