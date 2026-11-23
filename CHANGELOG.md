# Changelog

本文件记录技能集的所有重要变更。版本号遵循 [Semantic Versioning](https://semver.org/)：
**MAJOR** = 门禁语义或交付物契约不兼容；**MINOR** = 新增阶段能力/门禁；**PATCH** = 文案与缺陷修复。

> 编号说明：仓库早期按 `0.x` 发布（`0.1.0` / `0.2.0`），对应说明文档中的 v1.0 / v1.1；
> 自本版起仓库版本与文档版本统一为 **v2.0.0**。

---

## [2.0.0] - 2026-11-24

**输出目录改造**：所有交付物、过程证据、状态文件从 `output/` 平铺改为按阶段分目录。
包含不兼容变更，升级前请先读 §Breaking 与 README §九。

### Breaking

- **`output/` 改为固定七目录**
  `00-flow/`、`01-requirements/`、`02-scheme-io-bom/`、`03-electrical/`、`04-scl/`、
  `05-sim-trace/`、`06-eval-archive/`。目录名是契约，不得改名、加空格、改大小写。
- **`flow_status.json` 升到 schema 2.0**
  新增 `layout_version: "2.0"`、`output_layout: "staged"`、`output_root`、`stage_dirs`；
  续跑时 `layout_version` 不是 `2.0` 判 `E00_LAYOUT_VERSION`，要求先迁移。
- **旧平铺文件不再被读取**
  `output/` 根目录存在旧交付物时判 `E00_LAYOUT_CONFLICT`；新旧并存不自动合并、不自动删除。
- **错误码 65 → 69**
  新增 `E00_LAYOUT_INVALID`、`E00_LAYOUT_CONFLICT`、`E00_LAYOUT_VERSION`、`E00_PATH_UNSAFE`。

### Changed

- **7 个 SKILL.md**：输入输出契约、门禁、示例、模板、自检清单全部改为阶段路径；
  阶段 0 只创建 `00-flow/`，阶段 1～6 进入时创建各自目录；过程证据收敛到本阶段 `_work/`。
- **阶段 3**：新增 `plc_tag_table.xml`（供 `ImportPlcTagTable` 使用），与 `plc_tag_map.csv` 同源；
  `io_address.xlsx` 16 列、`terminal_list.xlsx` 10 列的口径保持不变。
- **阶段 4**：源码固定 `04-scl/src/`；`compilation_fix_shturl`、`db_definitions.xlsx`、
  `interface_contract.md` 固定 `04-scl/` 根；`src/使用说明/使用说明.md` 仍为推荐交付物（不阻断）。
- **阶段 5/6**：三件套输出到 `05-sim-trace/`、`06-eval-archive/`；过程脚本与中间文件放各自 `_work/`；
  阶段 6 统计输入优先 `./input/stage6_stats.json`，回退 `06-eval-archive/inputs/stats.json`。
- **归档**：`archive/<project_id>/` 与阶段目录一一对应；默认排除 `_work/`，`00-flow/` 默认不入归档。
- **校验脚本**：`check_stage4.py`、`check_stage5.py`、`validate_stage5.py`、`validate_stage6.py`、
  `stage6_collect.py`、`stage6_render.py` 的路径、`EXPECTED`、哈希输入键、报告模板同步改为阶段路径。
- **仓库工具**：`tools/ci_verify.py` 重写为布局契约自检；`tools/smoke_stage5.py` 夹具改为阶段目录；
  `tools/regen_sha.py` 覆盖 6 个校验脚本。

### Added

- `docs/自动化项目六阶段技能集说明文档_v2.0.md/.docx/.pdf`（49 页，含输出布局与迁移章节）。
- `docs/分阶段输出目录改造方案_v2.0.md`（v1.x → v2.0 的完整迁移依据）。
- 布局错误码与 `E00_PATH_UNSAFE` 路径越界防护。

### Verified

- `python tools/ci_verify.py`：125 项全部通过，0 失败。
- `python tools/smoke_stage5.py`：合格数据 `PASS/0`；判定时刻过早 `FAIL/1`；缺口行无依据 `FAIL/1`；
  阶段 6 缺输入 `FAIL/1|2`。
- 合成夹具：`check_stage4` / `check_stage5` / `validate_stage5` / `validate_stage6` PASS，
  `stage6_collect` 17/17，`stage6_render` 正常生成指标表与归档清单。

### Not verified

- 阶段 1–6 全链路实跑；真实 TIA Portal 导入/编译；PLCSIM 执行；旧平铺项目迁移实测。
- v1.x 自动迁移脚本未提供，需按 README §九 映射手工移动。

---

## [0.2.0] - 2026-11-16

本次为**门禁自洽性大修**：修掉正文与“附录 Z（实机回归失败模式）”两套规则并存导致的死锁，
并把跨技能断裂的列契约补齐。包含不兼容变更，升级前请先读 §Breaking。

### Breaking

- **`test_steps.csv` 6 列 → 8 列**
  新增 `前置态`、`判定时刻`（来自实机回归 T-02：缺前置态导致 15 条流程用例起不来；判定提前导致“期望 0”的用例假通过）。
  列序：`TEST-ID,关联REQ-ID,测试场景,输入激励,前置态,保持时间(ms),判定时刻,期望输出`。
  影响：`auto-flow-master-00` G5-02、`sim-trace-05` §3/§9/示例、`check_stage5.py` 的默认 profile。
- **`io_address.xlsx` 13 列 → 16 列**
  新增 `PLC符号`、`方向`、`NC语义`。原表没有符号名与极性，导致阶段 4 只能自造 `SIG_IO_xxx`（违反“不得自建 tag 表”），阶段 5 无法构造激励。
- **新增 `plc_tag_map.csv`（阶段 3 过程产物）**
  列：`IO-ID,Symbol,Address,DataType,Direction,NcSemantic,REQ-ID`。阶段 3 统一生成，阶段 4 用 `ImportPlcTagTable` 导入 PLC 变量表，**符号与地址一处生成、处处一致**。不计入阶段 3 的 6 项交付物，但缺失会阻断阶段 4。
- **`terminal_list.xlsx` 8 列 → 10 列**
  新增 `IO-ID`、`回路号`；`drawing_data.json` 的 `terminals[]` 同步加 `io_id`、`loop_id`、`terminal_no`。原表只有中文“信号名称”，阶段 5 只能靠字符串匹配建 IO→TERM 链，链路完整率永远到不了 100%。
- **阶段 4 的 `completion_scope` 固定追加 `+logic_unverified`**
  编译通过不等于逻辑正确；该后缀由阶段 5 完成“正常/急停/复位 ≥3 条已执行”后清除。

### Fixed

- **`auto-flow-master-00`**
  - 附录 Z 与正文冲突：`Z.2`（全未执行不得通过）已并入 G5-06“全部未执行”行，放行条件改为“每个候选通道都有具体失败证据”；`Z.1` 冒烟执行改归阶段 5（原写法要求阶段 4 使用尚未生成的阶段 5 用例，且与 §4 禁止逆序冲突）。
  - 状态枚举补齐：`stages[].status` 增加 `deviation`；`completion_scope` 增加 `+logic_unverified`，并固定拼接顺序。
  - §14 第 11 条原文两个 `partial` 混用（`test_scope` 与 `eval_scope`），已拆成三段独立判定。
  - G5-07 改为“从 `sim-trace-05/assets/` 复制 + 比对 SHA-256 + 首行 `PASS` + 退出码 `0`”；原写法要求一个并不存在的 `validate_stage5.py`。
  - G5-02/G5-03/G5-04 的表头从 `A | B | C` 写法改为逗号字面量与“列序固定”，避免误生成带竖线的 CSV。
  - `check_stage4.py`/`check_stage5.py` 挂载说明补充：退出码 `2` 同样不得判 PASS。
  - 编码门禁编号 `M-01~M-06` → `ENC-01~ENC-06`（与阶段 6 的指标 `M-01~M-14` 撞名）。
  - 删除模板中硬编码的本机路径，改为占位符；`capabilities.json` 纳入输出契约与阶段 0 门禁；工具契约补充 `ImportPlcTagTable` / `GetPlcTagTables`。
- **`req-spec-01`**
  - 默认模式自相矛盾：§1.3 写 `true`（默认），附录 C 写“用户未说模式 → 按 `false`”。已统一为 `true`，`false` 仅在编排层显式传入时生效。
  - REQ-ID 续号正则两套（`\d+` 与 `\d{3,}`）合并为 `\d{3,}`。
- **`scheme-io-bom-02`**
  - 附录 Z 要求“每点极性/前置类标记”，但 §5.1 锁定 9 列，二者互斥。已规定落位：极性写入 `电压电流规格` 后缀（`24VDC/NC`、`24VDC/NO`），前置类加 `信号名` 前缀 `[PRE]`。
  - 示例中的 `REQ-SAF-…` 不符合 REQ-ID 规范，改为 `REQ-001`。
- **`elec-construction-03`**
  - 补齐 `附录 Z`（此前 01/02/04/05/06 都有，唯独本技能没有）：`EL-01` 端子表必须带 `IO-ID`；`EL-02` NC/NO 逐点落表；`EL-03` 符号与 PLC 变量表同源；`EL-04` 备用率用未舍入值判定。
- **`plc-scl-gen-04`**
  - §2.2 符号来源改为阶段 3 的 `plc_tag_map.csv`（唯一来源），`SIG_` 兜底降级为“模拟模式下的临时映射，且不得覆盖阶段 3 原文件”；变量表通过 `ImportPlcTagTable` 导入，不再允许手写。
  - 块标题规则三层化：`S7_BlockTitle`/`S7_NetworkTitle` 必须 ASCII；变量行 `// 中文` 与块体注释必须中文；文件头注释块中文。消除“块标题禁止中文”与“块头标签用中文”的表面矛盾。
  - `Z.6` 从“必须先跑 3 条”改为“移交阶段 5”，与“不仿真、不调试”红线一致。
  - §4.5 与 §4.4 顺序倒置已修正；输入清单补充 `plc_tag_map.csv`。
- **`sim-trace-05`**
  - 校验器外置到 `assets/validate_stage5.py`（唯一事实源），删除正文内嵌的 84 行副本；新增 `assets/SHA256SUMS.txt`。
  - §8 自检原断言“所有链路的 `链路完整性` 必须为 `完整`”，与 §7.1“缺口行必须标 `部分`”互斥，改为“允许 `部分`，但备注必须写缺口依据”。
  - 四类工况判定原为 `“不适用” in 说明`（恒真），改为必须出现 `不适用：<类别>`。
  - 新增 §4.1.2 冒烟优先（3 条，失败即止）；§4.2 的 STOP→RUN 说明补充“Openness 不支持 RUN/STOP”。
  - results 与 CSV 的列比对从“前 5 列按位置”改为“按列名”，因为两边列序已不同。
- **`eval-archive-06`**
  - `M-11` 更名为 `综合追溯覆盖率`，与 `auto-flow-master-00` §12.3 G5-05 的字段名逐字对齐。
  - `M-12` 标注为占位指标（本流程不出图面，恒为 `未开展`），不计入“已计算”统计。
  - 合计工时公式改为 `人工工时 + 模型耗时 × k`，k 的默认值与来源必须在 `00-说明` 写明，否则记 `待统计`。
  - `validate_stage6.py` 补 `sys.exit`（原实现无论如何都退出 0）；“待统计 N 项”断言去掉 `or not missing` 短路。

### Added

- `tools/ci_verify.py`：仓库级一致性自检（frontmatter、代码围栏配对、跨技能列契约、枚举完整性、脚本 SHA-256 匹配等）。
- `tools/smoke_stage5.py`：用样本项目验证门禁双向行为（合格数据应 `PASS/0`，三类缺陷应 `FAIL/1|2`）。
- `tools/regen_sha.py`：改动 `assets/` 下脚本后重算 `SHA256SUMS.txt`。
- `README.md`、`LICENSE`、`.gitignore`、`.gitattributes`、`CHANGELOG.md`。
- 所有校验脚本统一 CLI 契约：首行 `PASS`/`FAIL`，明细 ` - ` 开头，退出码 `0/1/2`，stdout 强制 UTF-8。

### Removed

- 7 个技能目录下的历史备份 `.bak` / `_bak-*`（10 个文件，约 66 万字节），改由 git 历史承载。
- `__pycache__/`（运行产物，已加入 `.gitignore`）。

### Verified

- `tools/ci_verify.py`：全部通过。
- `tools/smoke_stage5.py`：合格数据 → `PASS/0`；判定时刻早于保持时间 → `FAIL/1`；缺口行无依据 → `FAIL/1`；阶段 6 缺输入 → `FAIL/2`。

---

## [0.1.0] - 2026-11-15

初版：六个阶段技能 + 总调度技能。每个技能包含目标与红线、输入输出契约、分步流程、交付前自检清单、对话输出契约与模板附录；总调度包含状态机、错误码表、断点续跑与用户报告模板。

同批加入**附录 Z：实机回归失败模式与强制检查**——由一次真实项目的实机回归（81 条用例）反推，记录“业务拒绝被当故障、NC 未取反、状态量用 Bool、用例缺前置态与判定时刻”等真实失败，并配套静态门禁脚本 `check_stage4.py` / `check_stage5.py`。

> 该附录最初以“增补”形式贴在正文之后，未回写正文门禁，导致与正文规则并存冲突；已在 0.2.0 中合并。