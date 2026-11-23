# ./output/06-eval-archive/_work/stage6_render.py
"""读取 eval_data.json，渲染 quality_metrics_summary.xlsx 与 project_archive_list.md。
只做格式化，不重新计算任何数值。"""
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font  # noqa: F401

OUT = Path("./output")
STAGE = OUT / "06-eval-archive" / "_work"
METRIC_HDR = ["指标ID", "维度", "指标名称", "指标值", "单位", "计算口径", "数据来源", "状态", "备注"]
COST_HDR = ["类别", "明细项", "数值", "单位", "单价(元)", "金额(元)", "数据来源", "状态", "备注"]
RISK_HDR = ["RISK-ID", "类别", "风险描述", "关联交付物", "风险等级", "判定依据", "应对措施", "状态"]
ARCH_HDR = ["阶段", "交付物", "相对路径", "状态", "SHA256", "版本/数据版本", "节点覆盖", "备注"]


def style(ws, widths, hdr):
    ws.append(hdr)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"
    for col, w in zip("ABCDEFGHI", widths):
        ws.column_dimensions[col].width = w


def wrap(ws):
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)


def main():
    data = json.loads((STAGE / "eval_data.json").read_text(encoding="utf-8"))
    fp = data["fingerprint"]
    project = data.get("project") or {}
    counts = data.get("counts", {})

    wb = Workbook()
    ws0 = wb.active
    ws0.title = "00-说明"
    rows = [
        ["项目", f"{project.get('id', '未记录')} {project.get('name', '')}".strip()],
        ["评估时间", data.get("generated_at", "—")],
        ["数据指纹", fp],
        ["评估版本", "EVAL-V1.0"],
        ["统计口径", "模型耗时=墙钟小时；人工=人时；合计=人工+模型(1:1折算)；成本=人民币"],
        ["基准", (data.get("time", {}).get("baseline") or {}).get("source", "未提供") + "（仅对比，不作为本项目数据）"],
        ["指标统计", f"已计算 {counts.get('computed', 0)} / 待统计 {counts.get('pending', 0)} / "
                     f"未开展 {counts.get('notrun', 0)} / 未执行 {counts.get('notexec', 0)}"],
        ["待统计明细", "；".join(f"{m['id']}({m['note']})" for m in data["metrics"]
                                if m["status"] == "待统计") or "无"],
        ["声明", "本表为评估数据，不构成验收/合规结论；未修改任何上游文件"],
    ]
    for r in rows:
        ws0.append(r)
    ws0.column_dimensions["A"].width = 16
    ws0.column_dimensions["B"].width = 100
    for row in ws0.iter_rows():
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    ws = wb.create_sheet("01-指标台账")
    style(ws, [8, 8, 26, 16, 6, 40, 40, 10, 40], METRIC_HDR)
    for m in data["metrics"]:
        ws.append([m["id"], m["dim"], m["name"], m["value"], m["unit"],
                   m["rule"], m["source"], m["status"], m["note"]])
    wrap(ws)

    wc = wb.create_sheet("02-工时成本")
    style(wc, [16, 30, 14, 8, 10, 14, 34, 10, 40], COST_HDR)
    for r in data["time"]["rows"] + data["cost"]["rows"]:
        wc.append(r)
    wrap(wc)

    wr = wb.create_sheet("03-风险清单")
    style(wr, [12, 14, 40, 34, 10, 40, 44, 12], RISK_HDR)
    for r in data["risks"]:
        wr.append([r["id"], r["cat"], r["desc"], r["artifact"],
                   r["level"], r["basis"], r["action"], r["status"]])
    wrap(wr)

    wa = wb.create_sheet("04-归档核对")
    style(wa, [8, 18, 40, 8, 24, 14, 18, 36], ARCH_HDR)
    for it in data["archive"]["items"]:
        wa.append([it["stage"], it["deliverable"], it["path"], it["status"],
                   (it["sha256"][:16] + "…") if it["sha256"] not in ("—", "") else "—",
                   it["version"], it["node"], it["note"]])
    wrap(wa)

    tmp = OUT / "06-eval-archive" / "quality_metrics_summary.tmp.xlsx"
    wb.save(tmp)
    tmp.replace(OUT / "06-eval-archive" / "quality_metrics_summary.xlsx")

    aw = data["archive"]
    items = aw["items"]
    lines = [
        "# 项目归档目录清单",
        "",
        f"- 项目：{project.get('id', '未记录')} {project.get('name', '')}".rstrip(),
        f"- 生成时间：{data.get('generated_at', '—')}",
        f"- 数据指纹：{fp[:16]}",
        f"- 归档版本：ARCHIVE-V1.0",
        f"- 归档完整率：{aw.get('complete_rate')}%（存在 {sum(1 for i in items if i['status'] == '存在')}/{len(items)}）",
        "",
        "## 1. 归档目录模板",
        "",
        "```text",
        "archive/<project_id>/",
        "├── 00-归档说明.md",
        "├── 01-requirements/",
        "├── 02-scheme-io-bom/",
        "├── 03-electrical/",
        "├── 04-scl/",
        "├── 05-sim-trace/",
        "├── 06-eval-archive/",
        "└── _manifest/SHA256SUMS.txt",
        "```",
        "",
        "## 2. 文件清单",
        "",
        "| 序号 | 阶段 | 交付物 | 相对路径 | 版本/数据版本 | 生成时间 | 责任人 | SHA256 | 状态 | 备注 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for it in items:
        digest = it["sha256"][:16] + "…" if it["sha256"] not in ("—", "") else "—"
        lines.append(f"| {it['seq']} | {it['stage']} | {it['deliverable']} | `{it['path']}` | "
                     f"{it['version']} | {it['mtime']} | {it['owner']} | {digest} | "
                     f"{it['status']} | {it['note']} |")
    lines += ["", "## 3. 六类追溯节点核对", "",
              "| 节点 | 矩阵内去重数 | 代表文件 | 状态 |", "|---|---|---|---|"]
    for node, files in aw.get("node_files", {}).items():
        cnt = aw.get("node_counts", {}).get(node, 0)
        status = "完整" if files else "部分（缺代表文件）"
        lines.append(f"| {node} | {cnt} | {', '.join(files) if files else '—'} | {status} |")
    lines += ["", "## 4. 缺失项", ""]
    if aw.get("missing"):
        lines += ["| 阶段 | 约定路径 | 状态 | 可能原因 | 补齐指引 |", "|---|---|---|---|---|"]
        for m in aw["missing"]:
            lines.append(f"| {m['stage']} | `{m['path']}` | {m['status']} | `{m['note']}` | "
                         f"回到阶段 {m['stage']} 重新产出并导出 |")
    else:
        lines.append("无缺失项。")
    lines += [
        "", "## 5. 复用模板", "",
        "- 目录：按 `01-requirements`…`06-eval-archive` 固定分层，阶段6 只放评估与归档产物。",
        "- 命名：沿用上游原文件名；归档说明与清单用 `00-` 前缀，不改名原件。",
        "- 版本：优先使用 `drawing_data.data_version` / `address_version`；无版本标 `未标注`，不伪造。",
        "- 校验：`_manifest/SHA256SUMS.txt` 记录相对路径与完整哈希，可用 `sha256sum -c` 校验。",
        "- 保留：按项目合同/企业制度确定，模板只给结构，不定制度。",
        "",
        "> 本清单只做归档评估，不移动/重命名任何上游文件；实际打包需用户确认后只读复制。",
        "",
    ]
    (OUT / "06-eval-archive" / "project_archive_list.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"quality_metrics_summary.xlsx / project_archive_list.md 已生成；指纹 {fp[:16]}")


if __name__ == "__main__":
    main()