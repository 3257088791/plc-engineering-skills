# ./output/06-eval-archive/_work/stage6_collect.py
"""采集五阶段交付物与补充统计，计算指标/工时/成本/风险/归档，输出 eval_data.json。
只读上游文件；所有数值必须能回指来源，缺数据标"待统计"。"""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook

OUT = Path("./output")
STAGE = OUT / "06-eval-archive" / "_work"
ROOT = Path(".")

EXPECTED = [
    (1, "需求规格表", "output/01-requirements/requirements_spec.xlsx", "REQ"),
    (1, "澄清日志", "output/01-requirements/clarification_shturl.md", "REQ"),
    (2, "控制方案", "output/02-scheme-io-bom/scheme.md", "—"),
    (2, "IO清单", "output/02-scheme-io-bom/io_list.xlsx", "IO"),
    (2, "BOM", "output/02-scheme-io-bom/bom.xlsx", "BOM"),
    (2, "多维自检报告", "output/02-scheme-io-bom/multi_check_report.md", "—"),
    (3, "IO地址表", "output/03-electrical/io_address.xlsx", "IO"),
    (3, "回路说明", "output/03-electrical/loop_description.md", "—"),
    (3, "电缆表", "output/03-electrical/cable_schedule.xlsx", "—"),
    (3, "端子表", "output/03-electrical/terminal_list.xlsx", "TERM"),
    (3, "强条自检", "output/03-electrical/clause_check.xlsx", "—"),
    (3, "统一数据源", "output/03-electrical/drawing_data.json", "IO/BOM/TERM"),
    (4, "SCL源文件", "output/04-scl/src/*.scl", "CODE"),
    (4, "编译修复日志", "output/04-scl/compilation_fix_shturl", "CODE"),
    (5, "测试步骤", "output/05-sim-trace/test_steps.csv", "TEST"),
    (5, "测试结果", "output/05-sim-trace/results.xlsx", "TEST"),
    (5, "追溯矩阵", "output/05-sim-trace/traceability_matrix.xlsx", "TEST"),
]

METRICS = []
TIME_ROWS = []
COST_ROWS = []
RISKS = []


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def num(v):
    if v is None:
        return None
    s = str(v).replace(",", "").strip()
    if not s or s in ("—", "-") or "待" in s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def pct(a, b):
    return round(a / b * 100, 2) if b else None


def read_rows(path, required, sheet=None):
    if not path.exists():
        raise FileNotFoundError(f"{path.name} 不存在")
    wb = load_workbook(path, data_only=True, read_only=True)
    sheets = [wb[sheet]] if sheet else wb.worksheets
    for ws in sheets:
        for i, row in enumerate(ws.iter_rows(min_row=1, max_row=20, values_only=True), 1):
            hdr = ["" if v is None else str(v).strip() for v in row]
            if all(x in hdr for x in required):
                out = []
                for r in ws.iter_rows(min_row=i + 1, values_only=True):
                    if r is None or all(v is None or str(v).strip() == "" for v in r):
                        continue
                    out.append({h: ("" if v is None else str(v).strip())
                                for h, v in zip(hdr, r)})
                if not out:
                    raise ValueError(f"{path.name} 表头匹配但无数据行")
                return out
    raise ValueError(f"{path.name} 未找到包含 {required} 的表头")


def metric(mid, dim, name, value, unit, rule, source, status="已计算", note=""):
    METRICS.append({"id": mid, "dim": dim, "name": name, "value": value,
                    "unit": unit, "rule": rule, "source": source,
                    "status": status, "note": note})


def safe(mid, dim, name, unit, rule, source, fn):
    try:
        value, note = fn()
        metric(mid, dim, name, value, unit, rule, source, "已计算", note)
    except Exception as e:  # 缺数据只降级，不中断
        metric(mid, dim, name, "待统计", unit, rule, source, "待统计",
               f"{type(e).__name__}: {e}")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    STAGE.mkdir(parents=True, exist_ok=True)
    now = datetime.now().isoformat(timespec="seconds")

    # ---------- 补充统计与统一数据源（先读，供归档版本/责任人使用） ----------
    stats = {}
    stats_source = "未提供"
    for p in (Path("./input/stage6_stats.json"), OUT / "06-eval-archive" / "inputs" / "stats.json"):
        if p.exists():
            try:
                stats = load_json(p)
                stats_source = str(p)
                break
            except Exception:
                stats = {}
    stats = stats or {}
    owners = stats.get("responsibility", {})
    dd = {}
    if (OUT / "03-electrical" / "drawing_data.json").exists():
        try:
            dd = load_json(OUT / "03-electrical" / "drawing_data.json")
        except Exception:
            dd = {}

    # ---------- 归档清单（最先，供 M-14 使用） ----------
    items = []
    for i, (stage, name, rel, node) in enumerate(EXPECTED, 1):
        p = ROOT / rel
        exists, size, mtime, digest, status, note = False, 0, "—", "—", "缺失", ""
        if rel.endswith("*.scl"):
            files = sorted((OUT / "04-scl" / "src").glob("*.scl"))
            exists = bool(files)
            size = sum(f.stat().st_size for f in files)
            mtime = datetime.fromtimestamp(files[0].stat().st_mtime).isoformat(timespec="seconds") if files else "—"
            digest = "—"
            note = f"{len(files)} 个文件" if files else "约定路径未发现 .scl"
        elif p.exists() and p.stat().st_size > 0:
            exists, size = True, p.stat().st_size
            mtime = datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")
            digest = sha(p)
        elif p.exists():
            status, note = "空文件", "文件存在但大小为 0"
        else:
            note = "约定路径未发现"
            alt = OUT / "01-requirements" / "clarification_shturl"
            if rel.endswith("clarification_shturl.md") and alt.exists():
                exists = True
                status = "存在"
                size = alt.stat().st_size
                mtime = datetime.fromtimestamp(alt.stat().st_mtime).isoformat(timespec="seconds")
                digest = sha(alt)
                note = "实际文件名：clarification_shturl"
        if exists:
            status = "存在"
        ver = "未标注"
        if dd and rel.endswith("drawing_data.json"):
            ver = "/".join(x for x in (dd.get("data_version"), dd.get("address_version")) if x) or "未标注"
        elif dd and rel.endswith("io_address.xlsx") and dd.get("address_version"):
            ver = dd["address_version"]
        items.append({"seq": i, "stage": stage, "deliverable": name, "path": rel,
                      "version": ver, "mtime": mtime,
                      "owner": owners.get(f"S{stage}", "未记录"),
                      "sha256": digest, "status": status, "note": note, "node": node})
    exist_n = sum(1 for it in items if it["status"] == "存在")

    # ---------- M-01 需求规格覆盖率 ----------
    def m01():
        rows = read_rows(OUT / "01-requirements" / "requirements_spec.xlsx", ["REQ-ID", "验收准则"])
        active = [r for r in rows if r.get("状态") != "已关闭"]
        need = ["REQ-ID", "需求内容", "验收准则", "优先级", "关联IO占位", "状态"]
        good = 0
        for r in active:
            crit = r.get("验收准则", "")
            if all(r.get(f, "").strip() for f in need) and not re.search(r"TBD|待确认|见现场", crit):
                good += 1
        return f"{pct(good, len(active)):.2f}%", f"完整 {good}/{len(active)}"

    safe("M-01", "需求", "需求规格覆盖率", "%",
         "六字段完整且非已关闭的REQ ÷ 非关闭REQ", "requirements_spec.xlsx", m01)

    # ---------- M-02 需求缺陷检出率 ----------
    def m02():
        p = OUT / "01-requirements" / "clarification_shturl.md"
        if not p.exists():
            p = OUT / "01-requirements" / "clarification_shturl"
        if not p.exists():
            raise FileNotFoundError("clarification_shturl(.md)")
        rows = [l for l in p.read_text(encoding="utf-8").splitlines()
                if re.match(r"^\|\s*Q-\d+", l.strip())]
        if not rows:
            raise ValueError("日志无结构化 Q- 问答行")
        closed = 0
        for line in rows:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 6 and cells[5] and "待" not in cells[5]:
                closed += 1
        return f"{pct(closed, len(rows)):.2f}%", f"已闭环 {closed}/{len(rows)}（以登记问题为分母）"

    safe("M-02", "需求", "需求缺陷检出率", "%",
         "已闭环需求问题 ÷ 澄清问题总数", "clarification_shturl.md", m02)

    # ---------- 共享数据 ----------
    bom_rows = []
    try:
        bom_rows = read_rows(OUT / "02-scheme-io-bom" / "bom.xlsx", ["BOM-ID", "型号"])
    except Exception:
        pass
    phys = []
    try:
        iol = read_rows(OUT / "02-scheme-io-bom" / "io_list.xlsx", ["IO-ID", "类型"])
        phys = [r for r in iol if r.get("类型") in ("DI", "DO", "AI", "AO")]
    except Exception:
        iol = []

    # ---------- M-03 IO点表准确率 ----------
    def m03():
        ioa = {r["IO-ID"]: r for r in read_rows(OUT / "03-electrical" / "io_address.xlsx", ["IO-ID", "物理地址"])}
        io_map = {i["io_id"]: i for i in dd.get("io", [])}
        addr = {a["io_id"]: a.get("address") for a in dd.get("addresses", [])}
        if not iol or not dd:
            raise ValueError("io_list 或 drawing_data 缺失")
        ok, fails = 0, []
        for r in phys:
            iid = r["IO-ID"]
            a = ioa.get(iid)
            good = bool(a) and a.get("类型") == r.get("类型")
            if good:
                good = str(addr.get(iid, "")) == str(a.get("物理地址", ""))
            if good and iid in io_map:
                s1 = {x for x in r.get("关联REQ-ID", "").replace("；", ";").split(";") if x}
                s2 = {x for x in str(io_map[iid].get("req_id", "")).replace("；", ";").split(";") if x}
                good = s1 == s2
            else:
                good = False
            ok += 1 if good else 0
            if not good:
                fails.append(iid)
        return f"{pct(ok, len(phys)):.2f}%", f"通过 {ok}/{len(phys)}" + \
            (f"；不符 {','.join(fails[:5])}" if fails else "；设备标签项按缺字段跳过")

    safe("M-03", "设计", "IO点表准确率", "%",
         "五项核对全过的物理IO ÷ 物理IO", "io_list.xlsx + io_address.xlsx + drawing_data.json", m03)

    # ---------- M-04 BOM完整率 ----------
    def m04():
        if not bom_rows:
            raise ValueError("bom.xlsx 缺失或无数据")
        fields = ["BOM-ID", "类别", "名称", "型号", "数量", "关联回路", "关联IO-ID"]
        good = sum(1 for r in bom_rows
                   if all(r.get(f, "").strip() for f in fields)
                   and (num(r.get("数量")) or 0) > 0)
        return f"{pct(good, len(bom_rows)):.2f}%", f"完整 {good}/{len(bom_rows)}"

    safe("M-04", "设计", "BOM完整率", "%",
         "字段完整且已关联的BOM条目 ÷ BOM条目", "bom.xlsx", m04)

    # ---------- M-05 器件型号有效率 ----------
    def m05():
        lib = read_rows(ROOT / "device_library.xlsx", ["型号"])
        models = {r["型号"].strip().lower() for r in lib if r.get("型号")}
        good = sum(1 for r in bom_rows if r.get("型号", "").strip().lower() in models)
        return f"{pct(good, len(bom_rows)):.2f}%", f"可回查 {good}/{len(bom_rows)}"

    safe("M-05", "设计", "器件型号有效率", "%",
         "型号可在器件库回查的条目 ÷ BOM条目", "bom.xlsx + device_library.xlsx", m05)

    # ---------- 强条 ----------
    clause_rows = []
    try:
        clause_rows = read_rows(OUT / "03-electrical" / "clause_check.xlsx", ["CLAUSE-ID", "初步判定"])
    except Exception:
        pass

    def m07():
        appl = [r for r in clause_rows if r.get("适用性") == "适用"]
        passed = [r for r in appl if r.get("初步判定") == "满足"]
        pending = sum(1 for r in appl if r.get("初步判定") == "待人工判定")
        return f"{pct(len(passed), len(appl)):.2f}%", \
            f"满足 {len(passed)}/{len(appl)}；待人工判定 {pending}"

    safe("M-07", "合规", "强条最终通过率", "%",
         "最终满足的适用条款 ÷ 适用条款", "clause_check.xlsx/初步判定", m07)

    def m06():
        appl = {r["CLAUSE-ID"] for r in clause_rows if r.get("适用性") == "适用"}
        if not appl:
            raise ValueError("无适用条款")
        try:
            remed = read_rows(OUT / "03-electrical" / "clause_check.xlsx", ["CLAUSE-ID", "整改前判定"],
                              sheet="02-整改记录")
        except Exception:
            remed = dd.get("remediation_log") or []
        if not remed:
            raise ValueError("无整改记录（首次判定不可得）")
        before = {}
        for r in remed:
            if isinstance(r, dict):
                cid = r.get("CLAUSE-ID") or r.get("clause_id")
                val = r.get("整改前判定") or r.get("before", "")
                if cid:
                    before[cid] = str(val)
        failed = sum(1 for cid in appl if before.get(cid, "") not in ("", "满足"))
        return f"{pct(len(appl) - failed, len(appl)):.2f}%", \
            f"首次满足 {len(appl) - failed}/{len(appl)}（未记录视为未整改）"

    safe("M-06", "合规", "强条自检首次通过率", "%",
         "首次判定满足的适用条款 ÷ 适用条款", "clause_check.xlsx/02-整改记录", m06)

    # ---------- 编译 ----------
    def compile_text():
        p = OUT / "04-scl" / "compilation_fix_shturl"
        if not p.exists():
            raise FileNotFoundError("compilation_fix_shturl")
        return p.read_text(encoding="utf-8", errors="replace")

    def m09():
        text = compile_text()
        if re.search(r"编译未执行|最终状态[^\n]*未执行", text):
            return "未执行", "日志结论：编译未执行"
        if re.search(r"编译通过", text):
            return "100.00%", "日志结论：编译通过（仅语法/接口）"
        if re.search(r"未通过|失败|转人工", text):
            return "0.00%", "日志结论：未通过"
        raise ValueError("日志无明确结论")

    def m08():
        text = compile_text()
        m = re.search(r"\|\s*0\s*\|[^|\n]*\|\s*(\d+)\s*\|", text)
        if not m:
            raise ValueError("无 Round 0 错误数")
        errs = int(m.group(1))
        return ("100.00%" if errs == 0 else "0.00%"), f"Round 0 错误数 {errs}"

    safe("M-09", "代码", "编译最终通过率", "%",
         "最终0错误=100%；失败=0%；未执行=未执行", "compilation_fix_shturl", m09)
    safe("M-08", "代码", "编译首次通过率", "%",
         "首次编译0错误=100%；否则0%", "compilation_fix_shturl/Round 0", m08)

    # ---------- M-10 测试 ----------
    test_rows = []
    try:
        test_rows = read_rows(OUT / "05-sim-trace" / "results.xlsx", ["TEST-ID", "判定结果"])
    except Exception:
        pass

    def m10():
        if not test_rows:
            raise ValueError("results.xlsx 缺失或无结果行")
        passed = sum(1 for r in test_rows if r.get("判定结果") == "通过")
        executed = sum(1 for r in test_rows if r.get("判定结果") in ("通过", "失败"))
        if executed == 0:
            return "未执行", "全部未执行"
        return f"{pct(passed, executed):.2f}%", \
            f"通过 {passed}/已执行 {executed}；总数 {len(test_rows)}"

    safe("M-10", "测试", "仿真测试步骤通过率", "%",
         "通过 ÷ 已执行（备注给总数口径）", "results.xlsx/01-测试结果", m10)

    # ---------- M-11 追溯 ----------
    def m11():
        wb = load_workbook(OUT / "05-sim-trace" / "traceability_matrix.xlsx", data_only=True)
        kv = {}
        if "00-说明" in wb.sheetnames:
            for r in wb["00-说明"].iter_rows(values_only=True):
                if r and r[0]:
                    kv[str(r[0]).strip()] = r[1]
        keys = ["需求测试覆盖率", "链路完整率", "结果覆盖率"]
        vals = []
        for k in keys:
            v = kv.get(k)
            if v is None:
                raise ValueError(f"00-说明 缺 {k}")
            vals.append(float(str(v).replace("%", "")))
        return f"{min(vals):.2f}%", "取三项最小值"

    safe("M-11", "追溯", "全链路追溯覆盖率", "%",
         "min(需求覆盖, 链路完整, 结果覆盖)", "traceability_matrix.xlsx/00-说明", m11)

    # ---------- M-12 图纸 ----------
    metric("M-12", "图纸", "图纸一次审核通过率", "未开展", "%",
           "本流程未出图面", "drawing_data.json（仅结构化数据）", "未开展",
           "图面布局/排版需人工完成")

    # ---------- M-13 IO-BOM 关联 ----------
    def m13():
        if not phys:
            raise ValueError("无物理IO")
        bom_io = set()
        for r in bom_rows:
            for x in str(r.get("关联IO-ID", "")).replace("；", ";").split(";"):
                if x.strip():
                    bom_io.add(x.strip())
        for i in dd.get("io", []):
            if i.get("bom_id"):
                bom_io.add(i["io_id"])
        ok = sum(1 for r in phys if r["IO-ID"] in bom_io)
        return f"{pct(ok, len(phys)):.2f}%", f"已关联 {ok}/{len(phys)}"

    safe("M-13", "设计", "IO-BOM关联覆盖率", "%",
         "有BOM关联的物理IO ÷ 物理IO", "drawing_data.json + bom.xlsx", m13)

    # ---------- M-14 归档完整率 ----------
    metric("M-14", "归档", "归档完整率", f"{pct(exist_n, len(items)):.2f}%", "%",
           "存在交付物 ÷ 约定交付物(17项)", "文件系统 + 归档清单", "已计算",
           f"存在 {exist_n}/{len(items)}")

    # ---------- 工时 ----------
    stages = stats.get("stages", {})
    labels = {"S1": "需求", "S2": "方案/BOM", "S3": "电气", "S4": "代码", "S5": "仿真"}
    time_rows, model_sum, labor_sum = [], None, None
    model_ok = labor_ok = True
    for key in ["S1", "S2", "S3", "S4", "S5"]:
        d = stages.get(key, {})
        ms, lh = d.get("model_seconds"), d.get("labor_hours")
        mh = round(ms / 3600, 2) if isinstance(ms, (int, float)) else None
        hh = round(lh, 2) if isinstance(lh, (int, float)) else None
        if mh is None:
            model_ok = False
        else:
            model_sum = mh if model_sum is None else round(model_sum + mh, 2)
        if hh is None:
            labor_ok = False
        else:
            labor_sum = hh if labor_sum is None else round(labor_sum + hh, 2)
        time_rows.append({"stage": key, "model_h": mh, "labor_h": hh,
                          "source": d.get("source", "未记录")})

    total_h = round(model_sum + labor_sum, 2) if (model_ok and labor_ok) else None
    for r in time_rows:
        r["total_h"] = round(r["model_h"] + r["labor_h"], 2) if r["model_h"] is not None and r["labor_h"] is not None else None
        r["share"] = f"{r['total_h'] / total_h * 100:.2f}%" if (r["total_h"] is not None and total_h) else "待统计"

    baseline = stats.get("baseline") or {}
    base_h = baseline.get("labor_hours") if isinstance(baseline.get("labor_hours"), (int, float)) else None
    gain = round((base_h - labor_sum) / base_h * 100, 2) if (base_h and labor_ok and labor_sum is not None) else None
    TIME_ROWS = []
    for r in time_rows:
        TIME_ROWS.append(["模型耗时", f"{r['stage']} {labels[r['stage']]}",
                          r["model_h"] if r["model_h"] is not None else "待统计",
                          "小时", "", "", r["source"],
                          "已计算" if r["model_h"] is not None else "待统计", ""])
    for r in time_rows:
        TIME_ROWS.append(["人工工时", f"{r['stage']} {labels[r['stage']]}",
                          r["labor_h"] if r["labor_h"] is not None else "待统计",
                          "人时", "", "", r["source"],
                          "已计算" if r["labor_h"] is not None else "待统计", ""])
    TIME_ROWS.append(["模型耗时", "合计", model_sum if model_ok else "待统计", "小时",
                      "", "", stats_source if stats else "stats.json", "已计算" if model_ok else "待统计", ""])
    TIME_ROWS.append(["人工工时", "合计", labor_sum if labor_ok else "待统计", "人时",
                      "", "", stats_source if stats else "stats.json", "已计算" if labor_ok else "待统计", ""])
    TIME_ROWS.append(["合计工时", "人工+模型(1:1折算)", total_h if total_h is not None else "待统计",
                      "小时", "", "", "口径：折算系数1.0", "已计算" if total_h is not None else "待统计",
                      "仅流程时长参考"])

    # ---------- 成本 ----------
    bom_total, bom_pending = 0.0, 0
    for r in bom_rows:
        q, p, sub = num(r.get("数量")), num(r.get("单价")), num(r.get("小计"))
        if sub is None and q is not None and p is not None:
            sub = q * p
        if sub is None:
            bom_pending += 1
        else:
            bom_total += sub

    rate = stats.get("rates", {}).get("labor_cny_per_hour")
    labor_cost = None
    detail = stats.get("labor_detail") or []
    if detail:
        paid, unknown = 0.0, 0
        for d in detail:
            h = d.get("hours")
            rt = d.get("rate_cny_per_hour", rate)
            if isinstance(h, (int, float)) and isinstance(rt, (int, float)):
                paid += h * rt
            else:
                unknown += 1
        labor_cost = round(paid, 2) if unknown == 0 else None
    elif labor_ok and isinstance(rate, (int, float)):
        labor_cost = round(labor_sum * rate, 2)

    model_cost = None
    mdetail = stats.get("model_detail") or []
    if mdetail:
        vals = [d.get("cost_cny") for d in mdetail if isinstance(d.get("cost_cny"), (int, float))]
        model_cost = round(sum(vals), 2) if len(vals) == len(mdetail) else None
    else:
        vals = [d.get("model_cost_cny") for d in stages.values()
                if isinstance(d.get("model_cost_cny"), (int, float))]
        if len(vals) == len(stages) and vals:
            model_cost = round(sum(vals), 2)

    one_time = [o for o in (stats.get("one_time") or []) if isinstance(o.get("cost_cny"), (int, float))]
    one_total = round(sum(o["cost_cny"] for o in one_time), 2) if one_time else None

    direct_complete = (bom_pending == 0 and labor_cost is not None and model_cost is not None)
    direct = round(bom_total + (labor_cost or 0) + (model_cost or 0), 2)
    capacity = stats.get("project", {}).get("capacity")
    per_unit = round(direct / capacity, 2) if (direct_complete and isinstance(capacity, (int, float)) and capacity) else None
    per_io = round(direct / len(phys), 2) if (direct_complete and phys) else None

    COST_ROWS = [
        ["BOM成本", f"已知 {len(bom_rows) - bom_pending} 项 / 共 {len(bom_rows)} 项",
         len(bom_rows), "项", "", round(bom_total, 2), "bom.xlsx",
         "部分" if bom_pending else "已计算", f"待询价 {bom_pending} 项" if bom_pending else ""],
        ["设计人工成本", "工时×单价",
         labor_sum if labor_ok else "待统计", "人时", rate if isinstance(rate, (int, float)) else "待统计",
         labor_cost if labor_cost is not None else "待统计", "stats.json",
         "已计算" if labor_cost is not None else "待统计",
         "" if isinstance(rate, (int, float)) else "缺工时单价，金额待统计"],
        ["模型成本", "调用量×单价", "", "—", "",
         model_cost if model_cost is not None else "待统计", "stats.json",
         "已计算" if model_cost is not None else "待统计",
         "" if model_cost is not None else "缺模型调用成本明细"],
        ["单项目直接成本", "BOM+人工+模型", "", "元", "", 
         direct if direct_complete else f"已知部分合计 {direct}（不完整）",
         "本表计算", "已计算" if direct_complete else "部分",
         "" if direct_complete else "存在待统计/待询价项"],
        ["一次性建设成本", "器件库/强条库/脚本", len(one_time), "项", "",
         one_total if one_total is not None else "待统计", "stats.json",
         "已计算" if one_total is not None else "待统计", "不计入单项目直接成本"],
        ["单位成本", f"÷产能（{stats.get('project', {}).get('capacity_unit', '单位未定')}）",
         per_unit if per_unit is not None else "待统计", f"元/{stats.get('project', {}).get('capacity_unit', '单位')}",
         "", "", "本表计算", "已计算" if per_unit is not None else "待统计",
         "成本不完整或产能缺失时待统计"],
        ["单位成本", "÷物理IO点数", per_io if per_io is not None else "待统计", "元/点",
         "", "", "本表计算", "已计算" if per_io is not None else "待统计",
         "辅助口径"],
    ]

    # ---------- 风险 ----------
    lib_rows = []
    try:
        lib_rows = read_rows(ROOT / "device_library.xlsx", ["型号"])
    except Exception:
        pass

    def lead_days(text):
        pairs = re.findall(r"(\d+)\s*(?:-\s*(\d+))?\s*天", str(text or ""))
        days = [int(x) for pair in pairs for x in pair if x]
        return max(days) if days else None

    lib = {r["型号"].strip().lower(): r for r in lib_rows if r.get("型号")}
    rid = 0
    for r in bom_rows:
        model = r.get("型号", "").strip()
        info = lib.get(model.lower()) if model else None
        if not info:
            continue
        days = lead_days(info.get("交期"))
        if days is None or days < 30:
            continue
        rid += 1
        alt = str(info.get("替代料", "")).strip()
        RISKS.append({
            "id": f"RISK-{rid:03d}", "cat": "器件交期",
            "desc": f"{r.get('名称', model)} 交期约 {days} 天，影响装配/调试",
            "artifact": f"bom.xlsx/{r.get('BOM-ID')}；device_library/{model}",
            "level": "高" if days >= 45 else "中",
            "basis": f"器件库交期“{info.get('交期')}”解析为 {days} 天（阈值≥45高，30–44中）",
            "action": f"提前下单锁定；替代方案：{alt if alt else '库内无替代料记录'}",
            "status": "已识别"})

    req_text = ""
    try:
        req_text = " ".join(r.get("需求内容", "") + r.get("验收准则", "")
                             for r in read_rows(OUT / "01-requirements" / "requirements_spec.xlsx", ["REQ-ID", "验收准则"]))
    except Exception:
        pass
    checks = [
        ("运行模式完整性", ["手动", "检修", "旁路", "点动"], "中", "requirements_spec.xlsx"),
        ("作业安全规程", ["挂牌", "上锁", "LOTO", "双人确认", "许可"], "高", "requirements_spec.xlsx"),
        ("异常恢复", ["断电", "上电", "通讯恢复", "重启", "自恢复"], "高", "requirements_spec.xlsx"),
        ("外部接口", ["消防", "门禁", "上位机", "MES", "报警推送"], "中", "requirements_spec.xlsx"),
        ("验收与培训", ["验收", "培训", "竣工", "资料移交"], "低", "requirements_spec.xlsx"),
    ]
    for name, kws, level, art in checks:
        hit = [k for k in kws if k in req_text]
        if not req_text:
            continue
        if hit:
            continue
        rid += 1
        RISKS.append({"id": f"RISK-{rid:03d}", "cat": "需求遗漏",
                      "desc": f"未在需求表中发现“{name}”相关要求",
                      "artifact": art, "level": level,
                      "basis": f"关键词 {'/'.join(kws)} 未命中",
                      "action": "人工确认是否纳入；确认后回到阶段1修订并同步全链路",
                      "status": "待人工确认"})

    if not req_text:
        rid += 1
        RISKS.append({"id": f"RISK-{rid:03d}", "cat": "需求遗漏",
                      "desc": "需求规格表缺失或不可解析，遗漏风险无法评估",
                      "artifact": "requirements_spec.xlsx", "level": "中",
                      "basis": "文件缺失/表头不符", "action": "补齐需求表后重新评估",
                      "status": "待统计"})

    fixed = [
        ("交付规范", "drawing_data.json 仅结构化数据，无图面布局/图框/图层",
         "drawing_data.json", "中", "文件不含坐标/图框字段",
         "安排电气工程师按 EPLAN/CAD 规范出图并审核"),
        ("交付规范", "SCL 源文件需按目标 TIA 版本导入，版本不一致可能导入失败",
         "compilation_fix_shturl", "中", "编译日志记录的 TIA 版本需与目标环境核对",
         "导入前核对 TIA 版本；必要时按目标版本重编"),
        ("交付规范", "交付物无统一版本号/日期标注",
         "output/ 全部交付物", "低", "文件名与内容未发现版本标识",
         "按归档模板补版本与日期（不修改内容，另建说明）"),
    ]
    for cat, desc, art, level, basis, action in fixed:
        rid += 1
        RISKS.append({"id": f"RISK-{rid:03d}", "cat": cat, "desc": desc,
                      "artifact": art, "level": level, "basis": basis,
                      "action": action, "status": "已识别"})

    # ---------- 归档覆盖 ----------
    matrix_rows = []
    try:
        matrix_rows = read_rows(OUT / "05-sim-trace" / "traceability_matrix.xlsx",
                                ["REQ-ID", "IO-ID", "TEST-ID"], sheet="01-追溯矩阵")
    except Exception:
        pass
    node_counts = {}
    for key in ("REQ-ID", "IO-ID", "BOM-ID", "TERM-ID", "CODE-ID", "TEST-ID"):
        node_counts[key.replace("-ID", "")] = len({r.get(key, "") for r in matrix_rows if r.get(key)})
    rep = {1: "output/01-requirements/requirements_spec.xlsx", 4: "output/04-scl/src/*.scl",
           5: "output/05-sim-trace/test_steps.csv"}
    coverage = {}
    for it in items:
        coverage.setdefault(it["node"], []).append(it["status"])
    missing = [it for it in items if it["status"] != "存在"]
    archive = {
        "items": items,
        "missing": [{"path": m["path"], "stage": m["stage"], "status": m["status"],
                     "note": m["note"]} for m in missing],
        "complete_rate": pct(exist_n, len(items)),
        "node_counts": node_counts,
        "node_files": {k: [i["path"] for i in items if k in i["node"] and i["status"] == "存在"]
                       for k in ("REQ", "IO", "BOM", "TERM", "CODE", "TEST")},
    }

    # ---------- 输入哈希 ----------
    inputs = {}
    for it in items:
        if it["path"].endswith("*.scl"):
            continue
        p = ROOT / it["path"]
        if p.exists() and p.is_file():
            inputs[it["path"]] = sha(p)

    counts = {
        "computed": sum(1 for m in METRICS if m["status"] == "已计算"),
        "pending": sum(1 for m in METRICS if m["status"] == "待统计"),
        "notrun": sum(1 for m in METRICS if m["status"] == "未开展"),
        "notexec": sum(1 for m in METRICS if m["status"] == "未执行"),
    }

    METRICS.sort(key=lambda m: m["id"])
    data = {
        "schema_version": "1.0",
        "generated_at": now,
        "project": stats.get("project", {}),
        "stats_source": stats_source if stats else "未提供",
        "inputs": inputs,
        "metrics": METRICS,
        "time": {"rows": TIME_ROWS, "model_h": model_sum if model_ok else None,
                 "labor_h": labor_sum if labor_ok else None, "total_h": total_h,
                 "baseline": baseline, "baseline_gain_pct": gain},
        "cost": {"rows": COST_ROWS, "bom_total": round(bom_total, 2),
                 "bom_pending": bom_pending, "labor_cost": labor_cost,
                 "model_cost": model_cost, "one_time": one_total,
                 "direct": direct, "direct_complete": direct_complete,
                 "per_unit": per_unit, "per_io": per_io, "capacity": capacity},
        "risks": RISKS,
        "archive": archive,
        "counts": counts,
    }
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
    data["fingerprint"] = hashlib.sha256(payload.encode()).hexdigest()
    (STAGE / "eval_data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"eval_data.json: 指标 {len(METRICS)} / 风险 {len(RISKS)} / "
          f"归档 {exist_n}/{len(items)} / 指纹 {data['fingerprint'][:16]}")


if __name__ == "__main__":
    main()