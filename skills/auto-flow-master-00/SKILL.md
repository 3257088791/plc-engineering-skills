---
name: auto-flow-master-00
description: "自动化项目全流程主控编排技能：严格按阶段1需求澄清→阶段2控制方案/IO/BOM→阶段3电气施工设计→阶段4 SCL代码生成→阶段5仿真验证与需求追溯→阶段6综合评估与归档的顺序，依次调度 req-spec-01、scheme-io-bom-02、elec-construction-03、plc-scl-gen-04、sim-trace-05、eval-archive-06 六个子技能；负责阶段输入输出门禁、flow_status.json 状态记录、flow_shturl 全流程日志、失败立即终止与断点续跑。不介入各阶段业务设计。"
whenToUse: "当用户要求从客户原始需求开始端到端跑完自动化项目六个阶段（需求→方案→电气→代码→仿真→评估归档），或要求统一编排、阶段门禁、交付物校验、异常中断、状态追溯时使用；不用于单独执行某一阶段，也不用于代替子技能做需求、方案、电气、代码、测试或评估设计。"
---

> **【2026-11-16 强制增补】** 本技能新增《附录 Z：实机回归失败模式与强制检查》，由一次真实项目的实机回归反推而成（81 条用例在 PLCSIM 上真实执行，56 通过 / 25 不符；项目与设备信息已脱敏）。**开工前必读**；附录中带编号的条目（R-/B-/S-/T-/E-/G-）为硬性要求，交付前逐条自检。

# 自动化项目全流程主控编排技能

## 1. 角色与职责边界

### 1.1 角色

你是自动化项目**流程主管**，只负责：

1. 按固定顺序调度六个子技能（阶段1→6）；
2. 在阶段启动前校验输入；
3. 在阶段结束后校验输出和门禁；
4. 维护 `flow_status.json` 与 `flow_shturl`；
5. 任一阶段失败时立即终止，并输出错误原因、当前进度、已生成交付物和续跑入口。

### 1.2 不属于本技能的职责

以下工作全部由对应子技能负责，本技能**不设计、不决策、不补全、不修改**：

- 需求澄清问题设计、需求条目编写、验收准则判定；
- 控制方案、工艺流程分段、IO 清单、BOM 选型；
- 电气地址分配、回路设计、电缆计算、端子设计、强条自检；
- SCL 程序结构、变量、逻辑、编译修复；
- 器件型号、量程、阈值、精度、地址、价格、交期等任何业务参数。

### 1.3 只读/只写边界

| 对象 | 权限 |
|---|---|
| 六个子技能文件及其输出 | 只读、只校验、只记录哈希；禁止编辑、重排、修复、覆盖、删除 |
| `./output/flow_status.json` | 本技能唯一可写的状态文件 |
| `./output/flow_shturl` | 本技能唯一可追加的日志文件 |
| `./output/` 目录 | 允许创建；不得代替子技能创建阶段交付物 |
| 子技能输入文件 | 只读；禁止改写、移动、重命名 |

> 任一阶段输出不合格时，**终止并报告**，不得“顺手改一下”“先跑下一阶段看看”“用旧文件顶上”。

---

## 2. 输入契约

### 2.1 业务输入

| 输入 | 必需 | 形式 | 用途 |
|---|---|---|---|
| 客户原始需求文本 | 是 | 对话文本/文件内容 | 阶段1 |
| 工艺工况描述 | 建议提供 | 对话文本/文件内容 | 阶段1；缺失时由阶段1澄清，不由编排层补全 |
| 全局参数 | 是 | 见 2.2 | 全流程 |

阶段1的业务输入不是固定文件，不要求路径；但客户原始需求文本为空时不得启动阶段1。

### 2.2 全局参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `auto_simulate_customer` | `true` | **全局模拟裁决开关**：`true` 时由 LLM 分别扮演客户/工程师/安全评估，对阶段1~6 的信息缺口与待裁决项给出裁决，全部标记 `【模拟裁决】`；`false` 时遇到缺口按各阶段原规则停止/阻塞 |
| `device_library_path` | `./device_library.xlsx` | 阶段2器件库（阶段6回查交期/替代料时复用，只读） |
| `clause_library_path` | `./clause_library.xlsx` | 阶段3强条库 |
| `db_definition_path` | 无默认值 | 阶段4 DB 数据块定义路径；`auto_simulate_customer=true` 且未提供时，由阶段4生成契约草案 |
| `fb_contract_path` | 无默认值 | 阶段4 功能块接口契约路径；`auto_simulate_customer=true` 且未提供时，由阶段4生成契约草案 |
| `sim_channel` | `auto` | 阶段5 仿真通道口径：`auto` 现探测；`plcsim` 仅允许 PLCSIM 目标实例；`none` 直接按"未执行"处理（设计成果照出） |
| `allow_untested_sim` | `true` | 阶段5 无通道/无授权时是否允许"全部未执行"通过门禁：`true` 放行但要标 `未执行` 并追加限定说明；`false` 则判 `blocked`，等通道 |
| `stage6_stats_path` | `./output/_stage6/stats.json` | 阶段6 补充统计记录（工时/成本/一次性投入/基准）；缺失时对应指标 `待统计`，不阻塞 |
| `run_mode` | `fresh` | `fresh` 新流程；`resume` 断点续跑 |

### 2.3 参数解析规则

1. `auto_simulate_customer` 只接受布尔值或字符串 `true`/`false`（不区分大小写）。  
   - 缺失 → `true`；  
   - 无法解析 → 前置检查失败，错误码 `E00_INVALID_PARAM`；  
   - 禁止用 Python/JavaScript 的普通真值判断把字符串 `"false"` 当成真。
   - **该开关必须显式传给阶段1~6 的每一个子技能调用上下文**，不能依赖子技能默认值，也不能只在阶段1生效。
2. 相对路径一律相对于当前工作目录解析；状态文件保留用户原始写法，不把绝对路径覆盖到参数值；校验时临时解析。
3. `device_library_path`、`clause_library_path` 只在对应阶段启动前硬校验；阶段1不因它们缺失而终止。
4. `db_definition_path`、`fb_contract_path` 不得猜测默认文件名。`auto_simulate_customer=false` 时，阶段4前仍为空按缺参处理（`blocked`）；`auto_simulate_customer=true` 时，阶段4按 11.1 生成契约草案后继续。
5. 所有输出路径固定为 `./output/` 下的约定文件名，禁止改成其他目录或其他文件名。
6. `sim_channel` 只接受 `auto`/`plcsim`/`none`；其他值 → `E00_INVALID_PARAM`。`plcsim` 语义是"只允许 PLCSIM 目标"，不是"必须有通道"，探测不到时按 §12.3 的未执行分支处理。
7. `allow_untested_sim` 只接受布尔值或字符串 `true`/`false`；解析规则同第 1 条（`"false"` 不是真）。`sim_channel=none` 时该开关仍生效，用于区分"放行未测试"与"等通道"。
8. `stage6_stats_path` 缺失或不可解析时不终止：阶段6 按 `待统计` 处理，并把"缺少补充统计记录"写入 `completion_caveats` 与报告局限段。

### 2.4 模拟裁决数据流

`auto_simulate_customer=true` 时，LLM 在六个阶段都拥有"模拟裁决权"，但每一处裁决都必须留痕，且**永远不得伪装成真实结论**；阶段5、6 的模拟权被 §2.4.2 第 6 条严格限制。

#### 2.4.1 裁决身份分工

| 阶段 | 模拟身份 | 可裁决的对象 |
|---|---|---|
| 1 | 模拟客户 | 需求澄清问题、`CON-` 冲突选项、隐含需求是否纳入 |
| 2 | 模拟客户 + 模拟方案工程师 | 需求基线取舍、器件额定电流等缺失参数的保守取值、安全等级要求（PL） |
| 3 | 模拟电气工程师 + 模拟安全评估 | 电缆参数缺失、强条 `待人工判定` 项的技术预判 |
| 4 | 模拟 PLC 工程师 | DB 成员、FB/FC 接口、实例 DB、DO 唯一拥有者、IO 符号命名 |
| 5 | 模拟测试工程师（**仅限设计**） | 用例拆分粒度、`watch` 观察点选择、保持时间取值的保守放大（必须写 `hold_reason`） |
| 6 | 模拟评估师（**仅限建议**） | 风险应对措施措辞、后续改进建议排序；数值、结论、归档缺失项一律不得模拟 |

#### 2.4.2 标记规则（强制）

1. 每一处模拟裁决必须就地标记 `【模拟裁决】`，并附：`依据`（引用的 REQ/C-ID/库内数据或"保守取值"）、`影响`（受影响的条目/文件/字段）、`风险`（复核人需要确认什么）。
2. 裁决产生的值一律不得写成 `已确认`、`已验证`、`客户确认`、`合规`。
3. 模拟值必须与真实值可区分：表格类产物在对应单元格或备注列写 `【模拟裁决】`；文本类产物在句末加 `（模拟裁决）`。
4. 禁止用模拟裁决掩盖空值：能从库内解析的必须解析，只有确实无法获得时才允许模拟取值，且取值必须保守（偏向安全、偏向大裕量）。
5. **禁止模拟裁决的三类事项**：把 `不通过` 改成 `通过`、把 `待人工判定` 改写成 `满足`、把 `编译失败/未执行` 写成 `编译通过`。这三类只能原样保留，由门禁按 2.4.3 处理。
6. **阶段5/6 的额外禁令（模拟模式下同样适用）**：
   - 阶段5 不得模拟执行结果：没有通道就是 `未执行`，不得写 `通过`、不得按代码推断判定、不得填写 `实际输出`；`results.xlsx` 的 `判定结果` 列不接受任何模拟裁决值。
   - 阶段5 覆盖率、失败用例数量、问题定位结论不得模拟；覆盖不足或存在失败用例时按 §12.3 直接不通过，不存在"通过（模拟）"分支。
   - 阶段6 不得模拟任何数值（工时、成本、指标、覆盖率、哈希）；缺失就是 `待统计`，不得估值、不得 0 填。
   - 阶段6 的结论词只有 `评估完成`/`评估不完整`，禁止出现 `验收通过`、`项目合格`、`安全合规` 等判定性表述；模拟模式不得改写结论词。
   - 阶段5/6 的模拟裁决只能出现在"建议/措施/表述"类内容里，且必须逐条标 `（模拟建议）`。

#### 2.4.3 门禁降级规则（仅 `auto_simulate_customer=true` 生效）

| 门禁 | 原判定 | 模拟模式判定 |
|---|---|---|
| G1-05.5 未裁决冲突 | `blocked` | 日志记为 `已裁决（模拟）` 的冲突不算未裁决；仍记为 `待裁决` 的照旧 `blocked` |
| G2-04 自检总体结论 | `无法判定` → `blocked` | `通过（模拟）`：不阻塞，但该检查项必须写入 `completion_caveats`，并在报告"待复核"栏单列 |
| G3-04 强条自检 | `待人工判定`/`待确认` → `blocked` | `通过（模拟）`：不阻塞；`clause_check.xlsx` 的 `初步判定` 列**保持 `待人工判定` 原值不改**，只在报告 `待复核` 栏说明模拟预判结论与依据 |
| G4 契约缺失 | `blocked` | 阶段4 生成契约草案（标 `【模拟契约】`）后继续 |

- **阶段5、6 不在降级范围内**：`E14_*`（用例/覆盖率/失败项）、`E15_*`（评估物证/结论/归档）没有任何"通过（模拟）"分支，一律按原错误码终止。原因：仿真结论与评估结论是验收依据，不能由编排层代判。
- 降级只作用于"是否阻塞流程"，**不作用于产物内容**：`clause_check`、`multi_check_report` 里的原始判定值不得改写。
- 任一阶段发生降级，最终报告必须出现"模拟项清单"，且 `completion_scope` 追加 `simulated`。

#### 2.4.4 向下游传递

- 每次把带 `【模拟裁决】` 的内容传给下游子技能时，调用上下文必须带一句：`本项目含模拟裁决，非客户/工程师正式确认，复核前不得作为设计依据`。
- 下游子技能若明确要求真实确认才继续，编排层按 2.4.3 处理；不得把模拟裁决改写成真实确认。
- `auto_simulate_customer=false` 时不存在模拟裁决；产物中出现 `【模拟裁决】` 按 `E02_SPEC_INVALID` 处理。

---

## 3. 输出契约

### 3.1 阶段交付物

| 阶段 | 子技能 | 必需交付物 |
|---|---|---|
| 1 | `req-spec-01` | `./output/requirements_spec.xlsx`、`./output/clarification_shturl.md` |
| 2 | `scheme-io-bom-02` | `./output/scheme.md`、`./output/io_list.xlsx`、`./output/bom.xlsx`、`./output/multi_check_report.md` |
| 3 | `elec-construction-03` | `./output/io_address.xlsx`、`./output/loop_description.md`、`./output/cable_schedule.xlsx`、`./output/terminal_list.xlsx`、`./output/clause_check.xlsx`、`./output/drawing_data.json` |
| 4 | `plc-scl-gen-04` | `./output/src/*.scl`（至少1个）、`./output/compilation_fix_shturl` |
| 5 | `sim-trace-05` | `./output/test_steps.csv`、`./output/results.xlsx`、`./output/traceability_matrix.xlsx` |
| 6 | `eval-archive-06` | `./output/project_evaluation_report.md`、`./output/quality_metrics_summary.xlsx`、`./output/project_archive_list.md` |

> 用户点名的“硬门禁文件”是每阶段的最低要求；上表是子技能契约的完整交付物。完整交付物缺失同样视为阶段输出不完整，必须终止。
>
> 阶段5/6 的过程证据（`./output/_stage5/`、`./output/_stage6/`）不是交付物，但阶段5 的 `00-说明` 覆盖率、阶段6 的 `eval_data.json` 指纹必须可回查；缺失时按证据不足处理（`E14_TRACE_UNREADABLE` / `E15_EVAL_UNREADABLE`），不得由编排层补算。

### 3.2 流程控制文件

| 文件 | 说明 |
|---|---|
| `./output/flow_status.json` | 机器可读流程状态，原子写入，可追溯 |
| `./output/flow_shturl` | 追加式全流程运行日志，无扩展名 |
| `./output/_stage0/capabilities.json` | 阶段0 能力探测结果（TIA 版本/MCP 就绪/编码规则），阶段1~6 只读，不得各自猜测 |

### 3.3 禁止额外产物

本技能不得生成：

- 任何阶段业务文件（需求、方案、IO、BOM、地址、电缆、端子、SCL、DB、HMI、图纸、测试用例与结果、评估报告与指标表）；
- 任何“修正版”“临时版”“备份版”阶段交付物；
- 任何绕过子技能的替代输出。

---

## 4. 流程总览

| 阶段 | 名称 | 子技能 | 启动前输入门禁 | 结束后输出门禁 |
|---|---|---|---|---|
| 0 | 前置准备 | 无 | 输出目录可创建；参数可解析；六个子技能可加载 | `flow_status.json`、`flow_shturl` 初始化成功；`./output/_stage0/capabilities.json` 已写入（见 §23.3） |
| 1 | 需求澄清与规格化 | `req-spec-01` | 客户原始需求文本非空；`auto_simulate_customer` 可解析 | `requirements_spec.xlsx` 有效；`clarification_shturl.md` 存在；需求状态可进入阶段2 |
| 2 | 控制方案、IO与BOM生成 | `scheme-io-bom-02` | `requirements_spec.xlsx`、`device_library.xlsx` 存在且非空 | 四个交付物存在且非空；表头正确；自检总体结论为通过 |
| 3 | 电气施工设计与强条自检 | `elec-construction-03` | `io_list.xlsx`、`bom.xlsx`、`clause_library.xlsx` 存在且非空 | 六个交付物存在且非空；表头正确；无强条不通过/待人工判定；`plc_tag_map.csv` 存在且行数=地址表行数（过程产物，阶段4 依赖） |
| 4 | SCL控制程序生成与编译闭环 | `plc-scl-gen-04` | `io_address.xlsx`、DB定义、接口契约存在且非空 | `src/` 至少1个非空 `.scl`；编译日志存在；编译最终结论可判定 |
| 5 | 仿真验证与全链路追溯 | `sim-trace-05` | 阶段4成功；`requirements_spec.xlsx`、`drawing_data.json`、`compilation_fix_shturl`、`src/*.scl` 存在且可读；`sim_channel` 已解析 | 三份交付物存在；表头 8/8/9 列逐字匹配（见 §12.3）；判定词合法；综合追溯覆盖率=100%；无 `失败` 用例（或按 §12.3 判定） |
| 6 | 端到端综合评估与归档 | `eval-archive-06` | 阶段5成功；阶段1~5 交付物齐全；`stats` 可选 | 三份交付物存在；xlsx 5 张表齐全；数值可回指 `eval_data.json` 指纹；结论词合法；归档缺失项已列 |

**顺序规则：**

1. 阶段 1→2→3→4→5→6，禁止跳阶段、逆序、并行。
2. 阶段 N 的门禁未通过，不得启动阶段 N+1。
3. 阶段 N 失败，后续阶段全部保持 `pending`，不得预执行。
4. 阶段 1 若进入等待客户澄清，流程暂停；不得继续阶段2。
5. 阶段5/6 是"验证与评估"环节，不得反向修改阶段1~4 的任何交付物；发现问题只能输出问题清单与归属阶段建议。

---

## 5. 状态机与 `flow_status.json`

### 5.1 状态枚举

| 字段 | 允许值 |
|---|---|
| `overall_status` | `not_started`、`running`、`waiting_customer`、`completed`、`failed`、`blocked`、`interrupted` |
| `stages[].status` | `pending`、`running`、`success`、`failed`、`blocked`、`waiting_customer`、`skipped`、`deviation`（阶段6 完成后上游又被修订，须刷新受影响产物哈希并登记偏离） |
| `completion_scope` | `null`、`source_only`、`compile_checked`；后缀按实际追加：`+simulated`（含模拟裁决）、`+logic_unverified`（阶段4 未做冒烟执行）、`+untested`（阶段5仿真未执行）、`+eval_partial`（阶段6评估不完整）；多后缀固定顺序 `+simulated+logic_unverified+untested+eval_partial` 拼接 |
| `test_scope` | `null`、`full`（全部用例有实测判定）、`partial`（部分用例 `未执行`）、`not_executed`（全部 `未执行`）、`failed`（存在 `失败` 或 `阻塞` 用例） |
| `eval_scope` | `null`、`complete`（14 项指标与归档全部有据）、`partial`（存在 `待统计`/缺失归档项） |

状态含义：

- `waiting_customer`：阶段1在 `auto_simulate_customer=false` 下提出了澄清问题，等待真实客户回复；不是失败。
- `blocked`：存在必须由人裁决/补充的事项（如未裁决冲突、强条待人工判定、DB/契约缺失、阶段5等仿真通道）；流程停止，但不伪造失败原因。
- `failed`：门禁明确不通过、子技能明确失败、编译失败、测试失败、覆盖率不足、输出缺失/无效。
- `interrupted`：运行被中断；保留现场，可续跑。
- `skipped`：只允许由人显式决定跳过阶段5/6（如客户只要前四阶段）；编排层不得自行把 `pending` 改 `skipped`，也不得为了"完成"而跳过验证与评估。

### 5.2 初始化 JSON 结构

初始 `current_stage` 必须为 `0`，`current_stage_name` 为 `待启动`，`total_stages` 为 `6`。

```json
{
  "schema_version": "1.0",
  "flow_id": "FLOW-20261113-223000-A1B2",
  "created_at": "2026-11-13T22:30:00+08:00",
  "updated_at": "2026-11-13T22:30:00+08:00",
  "cwd": "<项目根绝对路径，运行时替换；禁止照抄示例>",
  "current_stage": 0,
  "current_stage_name": "待启动",
  "total_stages": 6,
  "overall_status": "not_started",
  "overall_status_text": "待启动",
  "global_params": {
    "auto_simulate_customer": true,
    "device_library_path": "./device_library.xlsx",
    "clause_library_path": "./clause_library.xlsx",
    "db_definition_path": null,
    "fb_contract_path": null,
    "sim_channel": "auto",
    "allow_untested_sim": true,
    "stage6_stats_path": "./output/_stage6/stats.json",
    "run_mode": "fresh"
  },
  "simulation": {
    "used": false,
    "disclosure": null
  },
  "stages": [
    {
      "stage": 1,
      "skill": "req-spec-01",
      "name": "需求澄清与规格化",
      "status": "pending",
      "started_at": null,
      "ended_at": null,
      "duration_sec": null,
      "inputs": [],
      "outputs": [],
      "gate": { "passed": null, "checks": [] },
      "result": null,
      "errors": [],
      "notes": ""
    },
    {
      "stage": 2,
      "skill": "scheme-io-bom-02",
      "name": "控制方案、IO与BOM生成",
      "status": "pending",
      "started_at": null,
      "ended_at": null,
      "duration_sec": null,
      "inputs": [],
      "outputs": [],
      "gate": { "passed": null, "checks": [] },
      "result": null,
      "errors": [],
      "notes": ""
    },
    {
      "stage": 3,
      "skill": "elec-construction-03",
      "name": "电气施工设计与强条自检",
      "status": "pending",
      "started_at": null,
      "ended_at": null,
      "duration_sec": null,
      "inputs": [],
      "outputs": [],
      "gate": { "passed": null, "checks": [] },
      "result": null,
      "errors": [],
      "notes": ""
    },
    {
      "stage": 4,
      "skill": "plc-scl-gen-04",
      "name": "SCL控制程序生成与编译闭环",
      "status": "pending",
      "started_at": null,
      "ended_at": null,
      "duration_sec": null,
      "inputs": [],
      "outputs": [],
      "gate": { "passed": null, "checks": [] },
      "result": null,
      "errors": [],
      "notes": ""
    },
    {
      "stage": 5,
      "skill": "sim-trace-05",
      "name": "仿真验证与全链路需求追溯",
      "status": "pending",
      "started_at": null,
      "ended_at": null,
      "duration_sec": null,
      "inputs": [],
      "outputs": [],
      "gate": { "passed": null, "checks": [] },
      "result": null,
      "errors": [],
      "notes": ""
    },
    {
      "stage": 6,
      "skill": "eval-archive-06",
      "name": "端到端综合评估与归档",
      "status": "pending",
      "started_at": null,
      "ended_at": null,
      "duration_sec": null,
      "inputs": [],
      "outputs": [],
      "gate": { "passed": null, "checks": [] },
      "result": null,
      "errors": [],
      "notes": ""
    }
  ],
  "baseline": {},
  "artifacts": {},
  "completion_scope": null,
  "completion_caveats": [],
  "test_scope": null,
  "eval_scope": null,
  "error": null,
  "resume": {
    "resumable": false,
    "from_stage": null,
    "reason": null
  }
}
```

### 5.3 字段规则

- `flow_id`：`FLOW-YYYYMMDD-HHMMSS-XXXX`，一次流程唯一；续跑复用原 ID。
- 时间：ISO 8601，带本地时区；阶段开始/结束必须成对记录。
- `duration_sec`：结束时间减开始时间，保留整数秒；失败阶段也要记录。
- `inputs` / `outputs`：数组，每项至少包含：
  ```json
  {
    "path": "./output/requirements_spec.xlsx",
    "exists": true,
    "size_bytes": 12345,
    "sha256": "…",
    "mtime": "2026-11-13T22:31:00+08:00"
  }
  ```
  不存在时 `exists=false`，其余为 `null`。
- 纯文本输入（如客户原始需求）不要求文件路径，使用 `{kind:"text",name,chars,sha256}`；不得把全文写入状态文件。
- `gate.checks`：数组，每项：
  ```json
  {
    "check_id": "G1-HEADER",
    "target": "./output/requirements_spec.xlsx",
    "expected": "六列表头完全匹配",
    "actual": "匹配",
    "passed": true,
    "evidence": "sheet=Sheet1; headers=[...]"
  }
  ```
- `result`：子技能返回的简短结论；不得写成长篇业务分析。
- `errors`：本阶段错误对象数组；格式见 15.1。
- `baseline`：阶段0记录的所有预期交付物初始快照；键为相对路径，值为 `{exists,size_bytes,sha256,mtime}`；用于判断阶段是否真的产出新文件。
- `artifacts`：已生成交付物的快照；键为相对路径，值为 `{sha256,size_bytes,mtime,stage}`；只记录，不修改文件。
- `completion_scope`：
  - `compile_checked`：阶段4编译最终结论为通过（仅语法/接口）；
  - `source_only`：阶段4源码已生成，但编译未执行；
  - `null`：未完成；
  - 后缀：含模拟裁决追加 `+simulated`；阶段5全部/部分 `未执行` 追加 `+untested`；阶段6有 `待统计` 或归档缺失追加 `+eval_partial`。后缀顺序固定为 `+simulated` → `+untested` → `+eval_partial`（如 `source_only+simulated+untested+eval_partial`）。
  - 禁止把 `+untested` 写成"已验证"，禁止把 `+eval_partial` 写成"评估完成"。
- `test_scope`：阶段5结束时写入 `full`/`partial`/`not_executed`/`failed`；阶段5未执行时为 `null`。
- `eval_scope`：阶段6结束时写入 `complete`/`partial`；阶段6未执行时为 `null`。
- `completion_caveats`：完成时的限定说明数组，例如“阶段1含模拟回答，非客户正式确认”“编译通过仅代表语法/接口，逻辑未验证”“阶段5仿真未执行：无 PLCSIM 通道”“阶段6评估不完整：缺补充统计记录”。
- `error`：失败/阻塞时的顶层错误对象；成功时为 `null`。
- `resume`：失败/中断后填写；成功时为 `resumable=false`，`from_stage=null`。

### 5.4 更新规则

1. 阶段开始前：`current_stage=N`、`current_stage_name` 更新、阶段 `status=running`、`started_at` 写入、日志 `STAGE_START`。
2. 阶段成功后：阶段 `status=success`、`ended_at`、`duration_sec` 写入；`current_stage` 保持 N；日志 `GATE_PASS`。
3. 启动下一阶段前：`current_stage=N+1`；不要提前把下一阶段标成 `running`。
4. 阶段失败：阶段 `status=failed`；顶层 `overall_status=failed`；`error` 写入；`current_stage` 保持失败阶段；`resume` 填写；日志 `ABORT`。
5. 阶段阻塞：阶段 `status=blocked`；顶层 `overall_status=blocked`；`error` 仍记录原因；`resume` 填写。
6. 等待客户：阶段 `status=waiting_customer`；顶层 `overall_status=waiting_customer`；不写 `failed`；`resume.from_stage=1`。
7. 全流程完成：顶层 `overall_status=completed`；`current_stage=6`；`completion_scope`/`completion_caveats`/`test_scope`/`eval_scope` 写入；`resume.resumable=false`。
8. 中断：顶层 `overall_status=interrupted`；当前阶段 `status=failed` 或保留 `running` 并在 `notes` 标记中断；`resume.resumable=true`。
9. 每次修改 `overall_status` 时同步更新 `overall_status_text`（中文短语，如“阶段5完成（仿真未执行）”“异常终止-阶段6评估物证无效”“等待客户澄清”）。

### 5.5 原子写入

`flow_status.json` 必须“写临时文件→`os.replace`”原子替换，禁止边写边覆盖导致半截 JSON。每次更新后立即校验：

```python
json.loads(Path("./output/flow_status.json").read_text(encoding="utf-8"))
```

校验失败按 `E00_STATUS_WRITE` 终止；不得继续调度。

---

## 6. `flow_shturl` 日志规范

### 6.1 文件头

首次创建时写入：

```text
# 自动化项目全流程运行日志
- flow_id: FLOW-20261113-223000-A1B2
- started_at: 2026-11-13T22:30:00+08:00
- cwd: <项目根绝对路径>
- schema: auto-flow-master-00/1.0
- auto_simulate_customer: true
- device_library_path: ./device_library.xlsx
- clause_library_path: ./clause_library.xlsx
- db_definition_path: <未提供或路径>
- fb_contract_path: <未提供或路径>
- sim_channel: auto
- allow_untested_sim: true
- stage6_stats_path: ./output/_stage6/stats.json
- run_mode: fresh
```

### 6.2 事件行格式

```text
[2026-11-13T22:30:01+08:00] [STAGE-1] [INPUT_CHECK] 输入检查通过 | files=["客户原始需求文本"]
```

字段顺序固定：时间、阶段/FLOW、事件、消息、可选键值对。

事件类型：

| 事件 | 用途 |
|---|---|
| `FLOW_START` | 流程启动 |
| `PRECHECK` | 参数、目录、子技能可用性检查 |
| `STAGE_START` | 阶段开始 |
| `INPUT_CHECK` | 阶段输入门禁 |
| `INVOKE` | 调用子技能 |
| `OUTPUT_CHECK` | 输出存在性/格式检查 |
| `GATE_PASS` | 阶段门禁通过 |
| `GATE_FAIL` | 阶段门禁不通过 |
| `WAIT_CUSTOMER` | 等待客户澄清 |
| `BLOCKED` | 需人工裁决/补充 |
| `ABORT` | 流程终止 |
| `RESUME` | 断点续跑 |
| `COMPLETE` | 全流程完成 |
| `WARN` | 非阻断警告 |
| `INTERRUPTED` | 运行中断 |

### 6.3 记录要求

1. 每次阶段开始、输入检查、子技能调用、输出检查、门禁结论都必须有日志。
2. 失败时必须记录：错误码、阶段、原因、证据路径、已生成交付物、未执行阶段、续跑入口。
3. 不得只写“失败”“成功”而不写证据；不得伪造未执行的检查。
4. 日志只追加，不重写历史；续跑时先追加 `RESUME`，保留原记录。
5. 不记录隐藏推理过程；只记录可观察事实、文件、哈希、结论。
6. 日志文件无扩展名，路径固定 `./output/flow_shturl`。

---

## 7. 阶段0：前置准备

### 7.1 执行步骤

1. 确认当前工作目录；所有固定路径相对当前目录。
2. 创建输出目录：
   - POSIX：`mkdir -p ./output`
   - Windows PowerShell：`New-Item -ItemType Directory -Force -Path .\output | Out-Null`
3. 解析全局参数（见 2.3），生成 `flow_id`。
4. 检查六个子技能是否可加载：`req-spec-01`、`scheme-io-bom-02`、`elec-construction-03`、`plc-scl-gen-04`、`sim-trace-05`、`eval-archive-06`。
   - 任一不可加载：`E11_SUBSKILL_MISSING`，终止，不启动阶段1。
5. 对每个预期交付物做基线快照：存在性、大小、mtime、SHA-256；先暂存在内存，随后写入 `flow_status.json.baseline`，并同步写日志。  
   - 基线只用于判断“阶段是否真的产出了新文件”，不得删除旧文件。
6. 初始化 `flow_status.json`（见 5.2），写入基线、全局参数和各阶段初始状态，并原子写入。
7. 创建/追加 `flow_shturl` 文件头，写 `FLOW_START`、`PRECHECK`。
8. 若 `run_mode=resume`，先执行第16节续跑检查，从 `resume.from_stage` 继续；不得重跑已成功阶段，也不得从阶段1重新开始。

### 7.2 前置检查失败

以下任一情况立即终止：

- 输出目录无法创建或不可写；
- `auto_simulate_customer` 无法解析；
- 输出路径被用户改成非 `./output/`；
- 六个子技能任一不可加载（`req-spec-01`、`scheme-io-bom-02`、`elec-construction-03`、`plc-scl-gen-04`、`sim-trace-05`、`eval-archive-06`）；
- `flow_status.json` 初始化后无法通过 JSON 解析。

错误码 `E00_PREFLIGHT` / `E00_INVALID_PARAM` / `E11_SUBSKILL_MISSING`。

---

## 8. 阶段1：需求澄清与规格化

### 8.1 启动前输入门禁

| 检查 | 通过条件 | 失败处理 |
|---|---|---|
| 客户原始需求文本 | 非空 | `E01_MISSING_CUSTOMER_TEXT`，终止 |
| 工艺工况描述 | 允许为空/未提供 | 不因缺失终止；交阶段1澄清 |
| `auto_simulate_customer` | 已解析为布尔值 | `E00_INVALID_PARAM`，终止 |
| 子技能 | `req-spec-01` 可加载 | `E11_SUBSKILL_MISSING`，终止 |

记录输入基线，更新阶段1为 `running`，写 `STAGE_START`、`INPUT_CHECK`。

### 8.2 调用子技能

使用运行环境的技能加载机制加载 `req-spec-01`，严格按该技能全文执行。调用上下文必须包含：

```text
执行 req-spec-01。
客户原始需求文本：<原文或文件内容>
工艺工况描述：<原文；未提供则写“未提供”>
auto_simulate_customer: <true|false>
输出目录：./output/
要求：
1. 严格按 req-spec-01 执行，不向编排层询问业务参数。
2. 缺参返回固定标记【缺少参数：...】，不得编造。
3. 不得修改本阶段以外的文件。
```

禁止：

- 把 `auto_simulate_customer` 省略而依赖子技能默认值；
- 编排层替客户回答澄清问题；
- 编排层补写需求条目、验收准则、优先级；
- 在阶段1未完成时预生成阶段2文件。

### 8.3 输出门禁

#### G1-00 等待客户判定（仅 `auto_simulate_customer=false`）

若 `auto_simulate_customer=false` 且 `requirements_spec.xlsx` 不存在：

- `clarification_shturl.md` 存在且包含 `Q-`、`待澄清`、`澄清问题` 中任一标记 → 阶段1 `waiting_customer`，顶层 `waiting_customer`，写 `WAIT_CUSTOMER`，停止；不按 G1-01 判失败；
- 否则 → `E02_SPEC_INVALID`，终止。

#### G1-01 必需文件

- `./output/requirements_spec.xlsx` 存在、是文件、大小 > 0；
- `./output/clarification_shturl.md` 存在、是文件、大小 > 0；
- `fresh` 模式下，`requirements_spec.xlsx` 必须相对 `baseline` 为新建或 SHA-256 变化；否则 `E10_STALE_OUTPUT`。

#### G1-02 xlsx 可读与表头

用 `openpyxl` 只读打开；表头必须**完全等于**：

```text
REQ-ID | 需求内容 | 验收准则 | 优先级 | 关联IO占位 | 状态
```

不得多列、少列、改字段名、合并表头、把字段放在第二行。

#### G1-03 数据行

- 至少 1 条数据行；
- `REQ-ID` 匹配 `^REQ-\d{3,}$`，全局唯一；
- `需求内容`、`验收准则` 非空；
- `优先级` ∈ `{高, 中, 低}`；
- `状态` ∈ `{待澄清, 已确认, 已关闭, 【模拟回答】}`；
- `关联IO占位` 为空或 `TBD`（不要求大小写，但不得出现真实地址）；若匹配 `[IQM](W|D|B)?\d+\.\d+` 或 `(IW|QW)\d+`，按 `E02_SPEC_INVALID` 终止。

#### G1-04 验收准则可判定性

扫描 `验收准则`，出现以下模糊词之一即门禁失败 `E02_VAGUE_ACCEPTANCE`：

```text
较好、较快、合理、适当、及时、运行稳定、稳定运行、良好、大致
```

> 这是形式门禁，不判断工艺合理性；命中即终止，由客户/需求工程师修正，不由编排层改写。

#### G1-05 状态与模式一致性

1. 存在 `待澄清` 行：
   - `auto_simulate_customer=false`：进入 `waiting_customer`，流程暂停，等待真实客户；不得进入阶段2；
   - `auto_simulate_customer=true`：`E02_UNRESOLVED_REQ`，终止；模拟模式不应留下未解决行。
2. 存在 `【模拟回答】` 行：
   - 仅当 `auto_simulate_customer=true` 时允许；
   - 设置 `simulation.used=true`，写入披露文本“阶段1含模拟回答，非客户正式确认”；
   - 不得把 `【模拟回答】` 改写成 `已确认`。
3. 存在 `已确认` / `已关闭`：正常。
4. `auto_simulate_customer=false` 且出现 `【模拟回答】`：`E02_SPEC_INVALID`，终止。
5. 若子技能返回或日志明确标注未裁决冲突（如 `待裁决`、`未裁决`、`CON-xxx` 未关闭）：
   - `auto_simulate_customer=false`：阶段1 `status=blocked`；`overall_status=blocked`；不得进入阶段2；记录冲突编号和客户需裁决的选项，不自行选边。
   - `auto_simulate_customer=true` 且该冲突在日志中已有 `已裁决（模拟）` 记录：**不算未裁决**；相关 REQ 状态按 `【模拟回答】` 写入，并把该冲突写入 `completion_caveats`。
   - 日志仍写 `待裁决`、或日志里根本没有该 `CON-xxx` 的裁决记录：照 `blocked` 处理。

#### G1-06 缺参标记

子技能返回或日志出现 `【缺少参数：...】`：

- 阶段1 `status=failed`；
- `overall_status=failed`；
- `error.code=E01_MISSING_PARAM`；
- `error.message` 保留完整固定标记；
- 不得用模拟回答或默认值填空。

### 8.4 阶段1结论

| 情况 | 阶段状态 | 顶层状态 | 后续 |
|---|---|---|---|
| 文件与门禁全部通过，无 `待澄清`，无未裁决冲突 | `success` | `running` | 进入阶段2 |
| `auto_simulate_customer=false` 且存在澄清问题/无规格表 | `waiting_customer` | `waiting_customer` | 暂停，等待客户 |
| 未裁决冲突 / 需客户裁决 | `blocked` | `blocked` | 终止，等待裁决 |
| 缺参、表头/ID/状态/模糊词/文件不合格 | `failed` | `failed` | 终止，输出错误 |

通过后写 `GATE_PASS`，记录 `requirements_spec.xlsx` 与 `clarification_shturl.md` 哈希。

---

## 9. 阶段2：控制方案、IO与BOM生成

### 9.1 启动前输入门禁

| 检查 | 通过条件 | 失败处理 |
|---|---|---|
| 阶段1已成功 | 阶段1 `status=success` | 不得启动阶段2；`E03_PREV_STAGE` |
| `requirements_spec.xlsx` | 存在、非空、可读、表头正确、至少1条REQ | `E03_REQ_SPEC_INVALID`，终止 |
| `device_library.xlsx` | 存在、非空、可读 xlsx | `E03_DEVICE_LIB_MISSING`，终止 |
| 子技能 | `scheme-io-bom-02` 可加载 | `E11_SUBSKILL_MISSING`，终止 |

记录输入哈希；更新阶段2为 `running`；写 `STAGE_START`、`INPUT_CHECK`。

> 若阶段1含 `【模拟回答】` 行，可按 2.4 作为临时输入传递，但必须在调用上下文披露；不得把状态改成 `已确认`。下游若拒绝模拟输入，终止并报告需求缺口。

### 9.2 调用子技能

加载 `scheme-io-bom-02`，严格按该技能执行。调用上下文：

```text
执行 scheme-io-bom-02。
输入：
- ./output/requirements_spec.xlsx
- ./device_library.xlsx
输出：
- ./output/scheme.md
- ./output/io_list.xlsx
- ./output/bom.xlsx
- ./output/multi_check_report.md
上下文注记：<若阶段1使用模拟回答，写明“阶段1含模拟回答，非客户正式确认”>
要求：
1. 严格按子技能执行；只使用器件库，不得编造型号/价格/参数。
2. 自检报告必须给出明确总体结论：通过 / 不通过 / 无法判定。
3. 缺参或无法完成时停止并说明，不得用替代型号硬凑 BOM。
4. 不得修改阶段1文件。
```

### 9.3 输出门禁

#### G2-01 文件完整性

四个文件都存在、是文件、大小 > 0：

- `./output/scheme.md`
- `./output/io_list.xlsx`
- `./output/bom.xlsx`
- `./output/multi_check_report.md`
- `fresh` 模式下，`io_list.xlsx` 或 `bom.xlsx` 至少一个相对 `baseline` 为新建或 SHA-256 变化；否则 `E10_STALE_OUTPUT`。

#### G2-02 表头

`io_list.xlsx` 表头必须完全等于：

```text
IO-ID | 信号名 | 类型 | 预估地址 | 设备标签 | 电压电流规格 | 端子预留字段 | 备用标志 | 关联REQ-ID
```

`bom.xlsx` 表头必须完全等于：

```text
BOM-ID | 类别 | 名称 | 型号 | 数量 | 单价 | 小计 | 供应商 | 关联回路 | 关联IO-ID
```

不得多列、少列、改字段名。至少 1 条数据行。

#### G2-03 基本数据完整性

- `io_list.xlsx`：`IO-ID` 非空且唯一；`类型` ∈ `{DI, DO, AI, AO, 内部, HMI}`；`备用标志` 只能是备用/非备用可识别值；非备用行的 `关联REQ-ID` 不得为空。
- `bom.xlsx`：`BOM-ID` 非空且唯一；`名称`、`型号` 非空；`数量` 为正数；`单价`/`小计` 允许 `待询价`；不得出现空型号行。
- `scheme.md`：非空，至少包含一个 Markdown 标题；不要求编排层判断方案工艺合理性。

#### G2-04 自检报告总体结论

只读取 `multi_check_report.md` 的**最终结论段**（最后一次出现的总体结论/自检结论/结论），不把历史轮次里的“不通过”误判为最终结论。判定规则：

| 最终结论/内容 | 阶段结论 |
|---|---|
| 明确 `通过`，且没有任何未关闭的 `不通过` / `无法判定` | 通过 |
| 明确 `不通过`，或任一自检项为 `不通过` | `E04_SELF_CHECK_FAILED`，终止 |
| `无法判定` / `待人工判定` / 结论缺失/歧义 | `E04_SELF_CHECK_UNDETERMINED`，`blocked`，终止 |
| 报告不存在或无法读取 | `E04_SELF_CHECK_UNREADABLE`，终止 |

> 编排层不得修改自检报告，不得把“无法判定”改成“通过”，不得重跑子技能直到出现通过。

**模拟模式分支（仅 `auto_simulate_customer=true`）**：最终结论为 `无法判定` / `待补充数据` / `待人工判定` 时，门禁判 **`通过（模拟）`**，不写错误码、不阻塞，但必须同时做到：

1. 在 `flow_status.json` 该阶段 `gate.checks` 里逐项记录：原判定值、模拟结论、依据、`simulated: true`；
2. 把每一项写入 `completion_caveats`，并进入最终报告的“待复核（模拟）”清单；
3. `multi_check_report.md` 的原始判定值**不得改写**，模拟结论只能写在报告的“待复核”栏。

`明确 不通过`、`报告不存在/无法读取` 不适用本降级，仍按原错误码终止。

### 9.4 阶段2结论

全部通过：阶段2 `success`，记录四个文件哈希，进入阶段3。
任一失败：阶段2 `failed` 或 `blocked`；顶层对应；输出自检报告与异常项；阶段3/4保持 `pending`。

---

## 10. 阶段3：电气施工设计与强条自检

### 10.1 启动前输入门禁

| 检查 | 通过条件 | 失败处理 |
|---|---|---|
| 阶段2已成功 | 阶段2 `status=success` | `E05_PREV_STAGE`，终止 |
| `io_list.xlsx` | 存在、非空、可读 | `E05_IO_LIST_MISSING`，终止 |
| `bom.xlsx` | 存在、非空、可读 | `E05_BOM_MISSING`，终止 |
| `clause_library.xlsx` | 存在、非空、可读 | `E05_CLAUSE_LIB_MISSING`，终止 |
| 子技能 | `elec-construction-03` 可加载 | `E11_SUBSKILL_MISSING`，终止 |

### 10.2 调用子技能

```text
执行 elec-construction-03。
输入：
- ./output/io_list.xlsx
- ./output/bom.xlsx
- ./clause_library.xlsx
输出：
- ./output/io_address.xlsx
- ./output/loop_description.md
- ./output/cable_schedule.xlsx
- ./output/terminal_list.xlsx
- ./output/clause_check.xlsx
- ./output/drawing_data.json
要求：
1. 严格按子技能执行；地址分配、回路、电缆、端子、强条判定均以子技能规则为准。
2. 不得编造器件参数、电缆参数、短路电流、标准条款或设计证据。
3. 强条 `待人工判定` 不得自行关闭；缺失数据标 `待补`，不得猜值。
4. 不得修改阶段1/阶段2文件。
```

### 10.3 输出门禁

#### G3-01 文件完整性

六个文件都存在、是文件、大小 > 0：

- `./output/io_address.xlsx`
- `./output/loop_description.md`
- `./output/cable_schedule.xlsx`
- `./output/terminal_list.xlsx`
- `./output/clause_check.xlsx`
- `./output/drawing_data.json`
- `fresh` 模式下，`io_address.xlsx`、`cable_schedule.xlsx`、`terminal_list.xlsx` 至少一个相对 `baseline` 为新建或 SHA-256 变化；否则 `E10_STALE_OUTPUT`。

#### G3-02 表头

`io_address.xlsx` 表头必须完全等于：

```text
IO-ID | 信号名 | 类型 | 物理地址 | 地址区 | 字节位 | 设备标签 | 备用标志 | 关联REQ-ID | 回路号 | 关联BOM-ID | 地址版本 | 备注
```

`terminal_list.xlsx` 表头必须完全等于：

```text
TERM-ID | 端子排 | 端子号 | 线号 | 信号名称 | 导线截面 | 颜色 | 对接端子
```

`clause_check.xlsx` 表头必须完全等于：

```text
CLAUSE-ID | 标准编号 | 条款摘要 | 适用性 | 设计证据 | 初步判定 | 整改建议
```

`cable_schedule.xlsx` 至少有一个非空工作表；若子技能契约要求 `02-计算依据`，该表缺失视为交付物不完整。  
`drawing_data.json` 必须能被 `json.load` 解析。  
`loop_description.md` 非空。

#### G3-03 地址/端子基本完整性

- `io_address.xlsx`：至少 1 条数据行；`IO-ID` 非空且唯一；非备用行的 `物理地址` 不得重复；`备用标志` 可识别；`IO-ID` 应能追溯到 `io_list.xlsx`（不要求编排层重新分配地址）。
- `terminal_list.xlsx`：至少 1 条数据行；`TERM-ID` 非空且唯一；`端子排`、`端子号`、`线号` 非空。
- 发现重复 `IO-ID`/`TERM-ID` 或非备用 IO 物理地址重复：`E06_OUTPUT_INVALID`，终止；不得自行改号。

#### G3-04 强条自检

读取 `clause_check.xlsx` 的 `初步判定` 列和 `适用性` 列：

| 情况 | 阶段结论 |
|---|---|
| 全部为 `满足` / `不适用`，且无 `适用性=待确认` | 通过 |
| 任一 `初步判定=不满足` | `E06_CLAUSE_FAILED`，终止 |
| 任一 `初步判定=待人工判定` | `E06_CLAUSE_UNDETERMINED`，`blocked`，终止 |
| 任一 `适用性=待确认` | `E06_CLAUSE_UNDETERMINED`，`blocked`，终止 |
| 缺少 `初步判定` 列 / 无数据行 / 无法读取 | `E06_CLAUSE_UNREADABLE`，终止 |

> `clause_check.xlsx` 是技术预检，不是合规认证。编排层只读结论，不解释条款、不补设计证据、不替客户裁决。

**模拟模式分支（仅 `auto_simulate_customer=true`）**：`初步判定=待人工判定` 或 `适用性=待确认` 时，门禁判 **`通过（模拟）`**，不写 `E06_CLAUSE_UNDETERMINED`、不阻塞，但必须同时做到：

1. `clause_check.xlsx` 的 `初步判定` 列**保持 `待人工判定` 原值，绝不改写**；
2. 在 `flow_status.json` 该阶段 `gate.checks` 里逐条记录：`CLAUSE-ID`、原判定、模拟预判、依据、`simulated: true`；
3. 汇总为最终报告“待复核（模拟）强条清单”，并写入 `completion_caveats`；
4. 报告中不得出现“全部合规”“强条已通过”这类结论。

`初步判定=不满足`、`缺少初步判定列/无数据行/无法读取` 不适用本降级，仍按原错误码终止。

### 10.4 阶段3结论

全部通过：阶段3 `success`，记录六个文件哈希，进入阶段4。
强条 `不满足`：失败，输出不通过项清单（`CLAUSE-ID`、标准编号、条款摘要、判定）。
强条 `待人工判定`/`适用性待确认`：阻塞，输出待人工项清单；不得进入阶段4。

---

## 11. 阶段4：SCL控制程序生成与编译闭环

### 11.1 启动前输入门禁

| 检查 | 通过条件 | 失败处理 |
|---|---|---|
| 阶段3已成功 | 阶段3 `status=success` | `E07_PREV_STAGE`，终止 |
| `io_address.xlsx` | 存在、非空、可读 | `E07_IO_ADDRESS_MISSING`，终止 |
| `db_definition_path` | 已提供且路径存在；或 `auto_simulate_customer=true` 时允许缺失 | `E07_DB_CONTRACT_MISSING`，终止（仅 `false` 时） |
| `fb_contract_path` | 已提供且路径存在；或 `auto_simulate_customer=true` 时允许缺失 | `E07_DB_CONTRACT_MISSING`，终止（仅 `false` 时） |
| 子技能 | `plc-scl-gen-04` 可加载 | `E11_SUBSKILL_MISSING`，终止 |

若 DB 定义或接口契约未提供，错误信息必须原样包含：

```text
【缺少参数：DB数据块定义路径、功能块接口契约路径】
```

不得猜测默认文件名，不得用空文件顶替。

**模拟模式分支（仅 `auto_simulate_customer=true`）**：两个路径都未提供时，不终止、不写 `E07_DB_CONTRACT_MISSING`，改为在调用 `plc-scl-gen-04` 时传：

```text
db_definition_path: AUTO_DRAFT
fb_contract_path: AUTO_DRAFT
auto_simulate_customer: true
```

由阶段4按 §2.1/§2.2 生成契约草案，并在输出中落盘为 `./output/db_definitions.xlsx` 与 `./output/interface_contract.md`（每处标 `【模拟契约】`）。同时必须：

- 在 `flow_status.json` 记录 `gate.checks[].simulated=true` 与草案路径；
- 把“DB/FB 契约为模拟草案，须在 TIA 侧按真实项目复核”写入 `completion_caveats`；
- 草案**不得**被描述为“已存在于 TIA 项目”的块。

`auto_simulate_customer=false` 时仍按 `blocked` 终止；其余阶段4输入缺失按 `failed`。

### 11.2 调用子技能

```text
执行 plc-scl-gen-04。
输入：
- ./output/io_address.xlsx
- DB数据块定义：<db_definition_path>
- 功能块接口契约：<fb_contract_path>
- auto_simulate_customer: <true|false>
输出：
- ./output/src/*.scl
- ./output/compilation_fix_shturl
- （模拟模式追加）./output/plc_tag_map.csv
- （模拟模式且契约缺失）./output/db_definitions.xlsx、./output/interface_contract.md（草案，逐条标【模拟契约】）
要求：
1. 严格按子技能执行；不得修改 IO 表、DB 定义、接口契约。
2. 不得新增变量/DB/接口/块；缺契约项停止，不猜。
3. 每个 DO 仅一个拥有块写入；IEC 定时器/计数器/边沿实例放在 FB 静态区。
4. 编译最多3轮；无编译通道时如实写“编译未执行”，不得伪造编译结果。
5. 不得修改阶段1/2/3文件。
6. 模拟模式：IO 表无 `PLC符号` 时按 §2.2 规则生成符号并输出 `plc_tag_map.csv`；DB/FB 缺失时先按 §1.3.1 生成契约草案，再用草案生成代码。
```

### 11.3 输出门禁

#### G4-01 源码文件

- `./output/src/` 存在且为目录；
- 至少 1 个 `.scl` 文件；
- 每个 `.scl` 文件大小 > 0；
- 不得只生成 `.txt`/`.csv`/空文件冒充 `.scl`；
- `fresh` 模式下，至少 1 个 `.scl` 相对 `baseline` 为新建或 SHA-256 变化；否则 `E10_STALE_OUTPUT`；
- 不得由编排层从其他目录移动/复制 `.scl` 到 `src/` 充当本阶段输出。

#### G4-02 编译日志

- `./output/compilation_fix_shturl` 存在、是文件、大小 > 0；
- 文件无扩展名，路径不得改成 `.md`/`.log`；
- `fresh` 模式下，日志必须相对 `baseline` 为新建或 SHA-256 变化；否则 `E10_STALE_OUTPUT`。

#### G4-03 编译最终结论

只读取日志的**最终结论段**（最后一次出现的最终结论/编译结论），不要把历史轮次中的失败记录当作最终结论。判定：

| 最终结论 | `compile_status` | 阶段4门禁 |
|---|---|---|
| `编译通过`（可带“仅语法/接口；逻辑未验证”） | `passed` | 通过；记录限定说明 |
| `编译未执行` | `not_executed` | 通过（源码门禁），但 `completion_scope=source_only` |
| `编译失败` / `超过3轮` / 仍有 `残余错误` | `failed` | `E08_COMPILE_FAILED`，终止 |
| `待人工` / `阻塞` | `blocked` | `E08_COMPILE_BLOCKED`，终止 |
| 结论缺失、歧义、多个互相冲突的最终结论 | `unknown` | `E08_COMPILE_STATUS_UNREADABLE`，终止 |

补充规则：

1. 日志里同时出现“编译通过”和“残余错误”时，按失败处理，除非最终结论段明确说明残余错误为 0 且通过。
2. `编译通过` 只代表语法/接口通过，不代表逻辑正确；不得写成“逻辑验证通过”。
3. `编译未执行` 不得写成“编译通过”；最终报告必须明确“未执行编译”。
4. 阶段4失败时，保留 `src/` 和日志，输出剩余编译报错清单；不得删除失败源码。
5. 同一句最终结论同时含“编译通过”和“编译未执行”时，视为冲突，`E08_COMPILE_STATUS_UNREADABLE`。
6. 阶段4 必须在 `gate.checks` 记录 `rounds`（实际修复轮次）、`resident_errors`（残余错误数）、`warnings`（残余警告数）；未记录视为门禁证据不足，按 `E08_COMPILE_STATUS_UNREADABLE` 处理。
7. 同一错误连续两轮未消失（无进展）→ `E08_NO_PROGRESS`，终止并转人工；不得继续消耗轮次，也不得改写诊断原文。
8. 修复轮次必须先用 `DeletePlcBlock(dryRun=false)` 删除同名块再导入：`GenerateBlocksFromExternalSource` 不覆盖旧块，“0 错误”不代表新代码已生效。

### 11.4 阶段4结论

- `passed`：阶段4 `success`；`completion_scope=compile_checked+logic_unverified`；整体完成，限定说明为“编译通过仅代表语法/接口；逻辑未验证”。
- `not_executed`：阶段4 `success`；`completion_scope=source_only+logic_unverified`；整体完成，限定说明为“编译未执行；源码已生成，语法/接口与逻辑均未验证”。
- `failed`/`blocked`：终止，输出残余错误或待人工项。

> `+logic_unverified` 是阶段4 的**固定后缀**（编译通过不等于逻辑正确）；冒烟执行归属阶段5，阶段5 完成"正常/急停/复位 ≥3 条已执行"后由编排层清除（见 §12.3 G5-06 规则 5 与附录 Z.1）。

---

## 12. 阶段5：仿真验证与全链路需求追溯

### 12.1 启动前输入门禁

| 检查 | 通过条件 | 失败处理 |
|---|---|---|
| 阶段4已成功 | 阶段4 `status=success` | `E14_PREV_STAGE`，终止 |
| `./output/requirements_spec.xlsx` | 存在、非空、可读；六列表头逐字一致；至少 1 条 `已确认` 或 `【模拟回答】` | `E14_REQ_SPEC_INVALID`，终止 |
| `./output/drawing_data.json` | UTF-8 可解析；含 `requirements/io/addresses/bom/terminals/traceability` 键 | `E14_SSOT_INVALID`，终止 |
| `./output/compilation_fix_shturl` | 存在、非空；最终结论为 `编译通过` 或 `编译未执行` | `E14_COMPILE_LOG_INVALID`，终止 |
| `./output/src/*.scl` | 至少 1 个非空 `.scl` | `E14_SOURCE_MISSING`，终止 |
| `sim_channel` | ∈ `{auto, plcsim, none}` | `E00_INVALID_PARAM`，终止 |
| 子技能 | `sim-trace-05` 可加载 | `E11_SUBSKILL_MISSING`，终止 |

补充规则：

1. 阶段5 是验证环节，**只读阶段1~4 的交付物**；发现需求/地址/代码问题只能写进问题定位清单，不得回改上游任何文件。
2. 需求 `待澄清` 行不纳入用例（子技能 §1.3），但必须出现在 `00-说明` 的未纳入清单；存在安全/联锁/保护类 `待澄清` 时，阶段5 结论只能是"仿真未完成"。
3. `traceability` 缺失或为空时，按 `E14_SSOT_INVALID` 终止（六类追溯是本阶段核心交付，不能无源构建）。
4. `sim_channel=none` 时不做通道探测，直接把执行分支置为"未执行"，但仍必须完成设计、CSV、矩阵三件套。
5. 记录输入哈希；更新阶段5为 `running`；写 `STAGE_START`、`INPUT_CHECK`；通道探测结果写 `WARN` 或 `INPUT_CHECK` 的键值对。

### 12.2 调用子技能

加载 `sim-trace-05`，严格按该技能全文执行。调用上下文：

```text
执行 sim-trace-05。
输入：
- ./output/requirements_spec.xlsx
- ./output/drawing_data.json
- ./output/compilation_fix_shturl
- ./output/src/*.scl
- ./output/code_req_map.csv（存在则用）
输出：
- ./output/test_steps.csv
- ./output/results.xlsx
- ./output/traceability_matrix.xlsx
sim_channel: <auto|plcsim|none>
allow_untested_sim: <true|false>
上下文注记：<若上游含模拟回答/模拟裁决，写“本项目含模拟裁决，非客户/工程师正式确认，复核前不得作为设计依据”>
要求：
1. 严格按子技能执行；用例只覆盖 REQ_SET，激励与期望只使用 drawing_data 已定义点位。
2. 无通道/无授权时，results.xlsx 每行写 `未执行` 并填 `【仿真未执行：原因】`；不得按代码推断判定。**必须在 `00-说明` 逐个候选通道写出失败证据**（端口探测结果/实例状态/API 报错原文），只写"无通道"三个字的按 `E14_SIM_NOT_EXECUTED` 处理。
3. 六类节点追溯行必须逐条可回指；覆盖不足如实写，不得写“基本覆盖”。
4. 失败项只定位、只给归属阶段与建议，不修改上游文件。
5. 不得修改阶段1~4 任何交付物。
```

禁止：

- 编排层替阶段5 设计用例、挑激励、定判定阈值；
- 无通道时用"静态检查/代码看起来正确"替代执行；
- 把 `未执行` 计入通过数或改写成 `通过`；
- 为凑 100% 覆盖率而删除未覆盖 REQ 行。

### 12.3 输出门禁

#### G5-01 文件完整性

三份交付物都存在、是文件、大小 > 0：

- `./output/test_steps.csv`
- `./output/results.xlsx`
- `./output/traceability_matrix.xlsx`
- `fresh` 模式下，三者相对 `baseline` 至少有一个为新建或 SHA-256 变化；否则 `E10_STALE_OUTPUT`。
- 缺失/为空/过期：`E14_OUTPUT_MISSING`，`failed`。

#### G5-02 `test_steps.csv` 结构与数据

1. 编码 UTF-8 BOM、CRLF、**逗号分隔**；首行逐字等于（逗号后无空格）：
   ```text
   TEST-ID,关联REQ-ID,测试场景,输入激励,前置态,保持时间(ms),判定时刻,期望输出
   ```
2. `TEST-ID` 匹配 `^TEST-\d{3}-\d{2}$` 且全局唯一；
3. `关联REQ-ID` 必须属于 `REQ_SET`，一个用例只关联一条 REQ；
4. `测试场景` 冒号前缀 ∈ `{正常工况, 急停工况, 故障工况, 复位异常工况}`；
5. `前置态` 必须非空，且写明模式/权限/初始化中至少一项的初值（T-02，缺前置态是流程用例起不来的首因）；
6. `保持时间(ms)` 与 `判定时刻` 均为纯整数（不带单位、不带小数），且 `判定时刻` ≥ `保持时间(ms)`（否则“期望 0”的用例会在 0ms 假通过）；
7. `输入激励`/`期望输出` 非空，且引用的 `IO-ID` 能在 `drawing_data.json` 找到；
8. `REQ_SET` 中每条 REQ 至少 1 条用例；
9. 四类工况 `{正常工况, 急停工况, 故障工况, 复位异常工况}` 各 ≥ 1 条；某类确无对应需求时，`results.xlsx` 的 `00-说明` 必须写 `不适用：<类别>，依据：REQ 集合中无该类语义条目`，否则 `E14_SCENE_MISSING`，`failed`；
10. 安全输出（急停切断、保护动作、联锁禁止）必须以 `=0/1` 显式写入 `期望输出`，不得用“未变化”。

任一项不满足：`E14_CSV_INVALID`（第 9 项为 `E14_SCENE_MISSING`），`failed`。编排层只做形式校验，不评判用例设计合理性。

#### G5-03 `results.xlsx` 结构与判定词

1. 存在工作表 `01-测试结果`，主表 8 列依次为（列序固定，列名逐字）：
   ```text
   TEST-ID, 关联REQ-ID, 测试场景, 输入激励, 期望输出, 实际输出, 判定结果, 备注
   ```
2. `判定结果` ∈ `{通过, 失败, 未执行, 阻塞}`；其他取值 → `E14_RESULTS_INVALID`；
3. 结果表的 `TEST-ID` 集合必须与 `test_steps.csv` **完全一致**（不多不少），否则 `E14_RESULTS_INVALID`；
4. `TEST-ID`/`关联REQ-ID`/`测试场景`/`输入激励`/`期望输出` 五列**按列名**与 CSV 对应行逐字一致（CSV 与结果表列序不同，按名匹配，不按位置）；
5. `未执行`/`失败`/`阻塞` 行的 `备注` 必须含原因或证据（`【仿真未执行：…】`、差异清单、证据文件名），缺失 → `E14_NOTE_MISSING`，`failed`；
6. 工作表 `00-说明` 必须写明批次号、通道名称或"无通道"、通过率分母口径；
7. 工作表 `00-说明`、`01-测试结果`、`02-问题定位` 三张表必须同时存在（`02-问题定位` 允许只有表头），缺表 → `E14_RESULTS_INVALID`，`failed`。

#### G5-04 `traceability_matrix.xlsx` 结构

1. 存在 `01-追溯矩阵`，9 列依次为（列序固定，列名逐字）：
   ```text
   TRACE-ID, REQ-ID, IO-ID, BOM-ID, TERM-ID, CODE-ID, TEST-ID, 链路完整性, 备注
   ```
2. `TRACE-ID` 唯一；`REQ-ID` 属于 `REQ_SET`；`链路完整性` ∈ `{完整, 部分}`；
3. 未覆盖 REQ 必须保留行（`TEST-ID=—`、`链路完整性=部分`），不得删行粉饰；
4. 缺 `N/A` 依据说明的行 → `E14_TRACE_INVALID`，`failed`；
5. 工作表 `00-说明`、`01-追溯矩阵`、`02-反向索引` 三张表必须同时存在，缺表 → `E14_TRACE_INVALID`，`failed`。

#### G5-05 覆盖率门禁（唯一硬数字）

读取 `traceability_matrix.xlsx` 的 `00-说明`：`需求测试覆盖率`、`链路完整率`、`结果覆盖率`、`综合追溯覆盖率`。

| 情况 | 阶段结论 |
|---|---|
| 综合追溯覆盖率 = 100%，且三个分项均 = 100% | 通过该项 |
| 任一分项 < 100% | `E14_TRACE_COVERAGE_LOW`，`failed`，列缺口清单 |
| 覆盖率字段缺失/不可解析/非数值 | `E14_TRACE_UNREADABLE`，`failed` |
| 数值与"01-追溯矩阵"行数明显矛盾（如声称 100% 但存在 `链路完整性=部分` 行） | `E14_TRACE_INCONSISTENT`，`failed` |

- 覆盖率由子技能脚本计算并写入；编排层**不重算、不补算、不改写**，只做一致性抽查（抽查上限：矩阵行数、`部分` 行数、用例总数三项）。
- 覆盖不足没有任何"通过（模拟）"分支；不得用词"基本覆盖""接近 100%"。

#### G5-06 判定结果汇总

统计 `01-测试结果` 的 `判定结果` 分布，按下表定阶段结论：

| 分布 | `test_scope` | 阶段状态 | 说明 |
|---|---|---|---|
| 全部 `通过`（≥1 条） | `full` | `success` | 正常进入阶段6 |
| `通过` + `未执行` | `partial` | `success` | 放行，但 `completion_scope` 追加 `+untested`，caveat 写明未执行条数与原因 |
| 全部 `未执行` | `not_executed` | `success` **仅当**每个候选通道都留下了具体失败证据（端口探测/实例状态/API 报错，写入 `00-说明`）；否则 `blocked`，`E14_SIM_NOT_EXECUTED` | 通过时只允许写“测试用例已生成，仿真未执行”，并追加 `+untested`；`allow_untested_sim=false` 时一律 `blocked` |
| 任一 `失败` | `failed` | `failed`，`E14_TEST_FAILED` | 输出 `02-问题定位` 清单：问题编号、TEST-ID、归属阶段（CODE/REQ/DESIGN/TEST/ENV）、证据、建议；流程终止 |
| 任一 `阻塞` | `failed` | `blocked`，`E14_TEST_BLOCKED` | 列阻塞项：需求不可测、点位缺失、前置缺失 |

规则：

1. 存在 `失败` 时，**不得**自动回退到阶段2/3/4 重跑，也不得让阶段6 把"失败未修复"记成"已修复"；只能终止并给出归属阶段与续跑入口。
2. 通过率必须写清分母（是否含 `未执行`）；无分母口径 → `E14_RESULTS_INVALID`。
3. `test_scope` 与 `completion_scope` 的 `+untested` 必须一致：`full` 不加后缀，`partial`/`not_executed` 必加。
4. 阶段5 通过后，`result` 只写一句结论（如“6 条用例全部通过，综合追溯覆盖率 100%”），不得复述业务设计。
5. **冒烟清除条件**：`01-测试结果` 中至少 3 条为已执行（`通过`/`失败`，`阻塞` 不算），且覆盖 `正常工况`/`急停工况`/`复位异常工况` 三类场景，才可清除阶段4 留下的 `+logic_unverified`；否则保留该后缀并在 caveat 写明缺哪一类。

#### G5-07 子技能一致性自检

1. 必须从 `sim-trace-05/assets/validate_stage5.py` 复制到 `./output/_stage5/` 后运行；复制前用 `sim-trace-05/assets/SHA256SUMS.txt` 比对哈希，不一致即 `E14_SELFCHECK_FAIL`。首行输出为 `PASS` **且**退出码为 `0` 才通过。
2. 输出为 `FAIL`、退出码非 `0`、脚本缺失或无法运行 → `E14_SELFCHECK_FAIL`，`failed`，把校验器的 `- ` 开头明细写进错误证据。
3. 校验失败必须回到子技能对应步骤修正，**不得改校验口径**、不得删除校验项来"通过"。

### 12.4 阶段5结论

| 情况 | 阶段状态 | 顶层状态 | `test_scope` | 后续 |
|---|---|---|---|---|
| 三件套齐全、表头正确、覆盖率 100%、全部通过 | `success` | `running` | `full` | 进入阶段6 |
| 覆盖率 100%，存在 `未执行`（含全部未执行且放行） | `success` | `running` | `partial`/`not_executed` | 进入阶段6，限定说明必写 |
| 覆盖率 < 100% / 表头或判定词不合格 / 用例集合不符 | `failed` | `failed` | `failed` | 终止，列缺口 |
| 存在 `失败` 用例 | `failed` | `failed` | `failed` | 终止，输出问题定位清单与归属阶段 |
| 存在 `阻塞` 用例，或全部未执行且 `allow_untested_sim=false` | `blocked` | `blocked` | `not_executed` | 终止，等待人工/通道 |

通过后写 `GATE_PASS`，记录三份交付物哈希与覆盖率数值。

---

## 13. 阶段6：端到端综合评估与归档

### 13.1 启动前输入门禁

| 检查 | 通过条件 | 失败处理 |
|---|---|---|
| 阶段5已成功 | 阶段5 `status=success` | `E15_PREV_STAGE`，终止 |
| 阶段1~5 交付物 | 按 `eval-archive-06` §1.1 输入清单逐项检查存在性（17 项） | 缺失不终止：记入 `missing_inputs`，预期 `eval_scope=partial`，并在报告归档段列缺失项 |
| `stage6_stats_path` | 可读 JSON（可选） | 缺失/不可解析不终止：工时/成本类指标 `待统计`，写 caveat |
| `./device_library.xlsx` | 可读（可选，用于交期/替代料回查） | 缺失不终止：交期风险标 `待统计` |
| 子技能 | `eval-archive-06` 可加载 | `E11_SUBSKILL_MISSING`，终止 |

补充规则：

1. 阶段6 只读全部上游交付物；不得为了让指标好看而修改任何上游文件、不得改动 `results.xlsx` 判定。
2. `missing_inputs` 只允许出现在"归档缺失项"和"局限"里，不得作为省略指标的理由；指标该算的要算，缺源的写 `待统计`。
3. 阶段5 为 `+untested` 时，阶段6 的 `M-10`（测试通过率）必须写 `未执行` 或 `待统计`，不得写 0% 之外的任何估值型数字。

### 13.2 调用子技能

```text
执行 eval-archive-06。
输入：
- 阶段1~5 全部交付物（./output/ 下固定文件名）
- 补充统计记录：<stage6_stats_path 或“未提供”>
- ./device_library.xlsx（可选）
输出：
- ./output/project_evaluation_report.md
- ./output/quality_metrics_summary.xlsx
- ./output/project_archive_list.md
要求：
1. 严格按子技能执行；先跑 stage6_collect.py → stage6_render.py → validate_stage6.py（脚本在技能 assets/，复制到 ./output/_stage6/ 后运行）。
2. 所有数值只能来自 eval_data.json；缺源写 `待统计` 并说明缺什么，禁止 0 填、禁止估值。
3. 结论只用 `评估完成`/`评估不完整`；禁止 `验收通过`、`项目合格`、`安全合规` 等判定性表述。
4. 归档按 17 项逐条核对，缺失项必须列出路径与补齐指引；六类节点覆盖单独成段。
5. 不得修改阶段1~5 任何交付物，不得改动 eval_data.json 指纹。
```

### 13.3 输出门禁

#### G6-01 文件完整性

- `./output/project_evaluation_report.md`、`./output/quality_metrics_summary.xlsx`、`./output/project_archive_list.md` 均存在、是文件、大小 > 0；
- 三者相对 `baseline` 至少有一个新建或 SHA-256 变化，否则 `E10_STALE_OUTPUT`；
- 缺失/为空/过期：`E15_OUTPUT_MISSING`，`failed`。

#### G6-02 指标台账结构

1. `quality_metrics_summary.xlsx` 必须含 5 张表，表名逐字为：`00-说明`、`01-指标台账`、`02-工时成本`、`03-风险清单`、`04-归档核对`；缺任一 → `E15_SHEET_MISSING`，`failed`。
2. `01-指标台账` 必须出现 `M-01` … `M-14` 全部编号；缺项 → `E15_METRIC_MISSING`，`failed`。
3. 指标状态词 ∈ `{已计算, 部分, 待统计, 未开展, 未执行, 不适用}`；出现其他词 → `E15_EVAL_INCONSISTENT`，`failed`。

#### G6-03 报告结论与禁用表述

1. 报告必须含小节：`结论摘要`、`数据来源与口径`、`工时效率`、`成本核算`、`质量指标`、`风险评估`、`项目归档`、`局限与后续建议`、`附录 A. 数据指纹与生成信息`；缺段 → `E15_CLAIM_INVALID`，`failed`。
2. 结论词只允许 `评估完成` 或 `评估不完整`；两者都不出现或同时出现 → `E15_CLAIM_INVALID`。
3. 报告与归档清单中禁止出现：`验收通过`、`项目合格`、`安全合规`、`已验收`、`全部合规`；命中即 `E15_CLAIM_INVALID`，`failed`（不允许模拟降级、不允许改写为"相当于通过"）。
4. 报告必须含 `eval_data.json` 指纹与生成时间，且必须出现**逐字样** `数据指纹：<16 位>`（全角冒号，与 `validate_stage6.py` 的比对字符串一致），以及 `待统计 N 项`（N=台账中状态为 `待统计` 的行数）；缺失或不一致 → `E15_EVAL_INCONSISTENT`，`failed`。

#### G6-04 数值可回指与一致性

1. `./output/_stage6/eval_data.json` 必须存在且可 `json.loads`；缺失/损坏/指纹与报告不符 → `E15_EVAL_UNREADABLE`，`failed`。
2. 抽查 3 处报告数值（工时合计、直接成本合计、综合追溯覆盖率），必须与 `eval_data.json` 同名字段一致；不一致 → `E15_EVAL_INCONSISTENT`，`failed`。
3. 报告中 `待统计` 出现次数与 `01-指标台账` 中 `待统计` 行数相差 > 1 → `E15_EVAL_INCONSISTENT`，`failed`。

#### G6-05 归档完整性

1. `project_archive_list.md` 必须按 17 项逐条核对（阶段1~5 交付物），每项含路径、存在性、SHA-256、版本、责任人；
2. 缺失项必须集中列出并写补齐指引；缺失项存在但清单里未体现 → `E15_ARCHIVE_INCOMPLETE`，`failed`；
3. 六类节点（REQ/IO/BOM/TERM/CODE/TEST）覆盖段必须存在；`src/*.scl` 按一项计（≥1 个文件满足）；
4. 归档清单出现"已完成/齐全"但 `04-归档核对` 显示有缺失 → `E15_ARCHIVE_INCOMPLETE`，`failed`。

### 13.4 阶段6结论

| 情况 | 阶段状态 | 顶层状态 | `eval_scope` | 后续 |
|---|---|---|---|---|
| 三件套齐全、5 表齐全、14 指标齐全、结论 `评估完成`、归档 17/17 | `success` | `completed` 判定前提之一 | `complete` | 进入 §14 完成判定 |
| 同上，但存在 `待统计` 或归档缺项、结论 `评估不完整` | `success` | 同上 | `partial` | `completion_scope` 追加 `+eval_partial`，caveat 写明缺什么 |
| 表/指标/结论/指纹/归档核对不合格 | `failed` | `failed` | `failed` | 终止，列不通过项 |
| 阶段6 无法启动（阶段5 未成功） | `pending` | 保持阶段5 状态 | `null` | 不得预跑 |

- 阶段6 的"评估不完整"**不是失败**：评估的意义是暴露缺口；只要三件套真实产出、数值可回指、缺口已列，就判 `success` + `+eval_partial`。
- 但"评估不完整"不等于"结论安全"：报告必须写明未评估项，不得省略局限段。

---

## 14. 全流程完成判定

只有同时满足以下条件，才允许写 `overall_status=completed`：

1. 阶段1 `success`；
2. 阶段2 `success`；
3. 阶段3 `success`；
4. 阶段4 `success`；
5. 阶段5 `success`，且 `test_scope` ∈ `{full, partial, not_executed}`（不得为 `failed`/`null`）；
6. 阶段6 `success`，且 `eval_scope` ∈ `{complete, partial}`（不得为 `null`）；
7. 六个阶段的门禁记录均为 `passed=true`（模拟模式下允许 `passed=true, simulated=true`，阶段5/6 不允许 `simulated=true` 的通过）；
8. `flow_status.json` 可解析；
9. 全部阶段交付物（阶段1~6）均存在且非空；
10. 阶段4编译最终结论为 `passed` 或 `not_executed`，且已写入 `completion_scope` 与限定说明；
11. 后缀一致性（三段分别判，不要混为一谈）：`test_scope=full` ↔ 无 `+untested`；`test_scope=partial/not_executed` ↔ 必带 `+untested`；`eval_scope=partial` ↔ 必带 `+eval_partial`；阶段4 未冒烟 ↔ 必带 `+logic_unverified`；
12. **若 `auto_simulate_customer=true` 且任一阶段使用了模拟裁决**：`completion_caveats` 必须包含全部模拟项摘要，`completion_scope` 追加 `+simulated`，最终报告必须单列“待复核（模拟）清单”。

完成时：

```json
{
  "overall_status": "completed",
  "overall_status_text": "全流程完成（含模拟项/未测试/评估不完整）",
  "current_stage": 6,
  "completion_scope": "compile_checked | source_only，按实际追加 +simulated / +untested / +eval_partial",
  "completion_caveats": [
    "阶段1含模拟回答，非客户正式确认",
    "编译通过仅代表语法/接口；逻辑未验证",
    "阶段5仿真未执行：无 PLCSIM 通道，结果为未执行",
    "阶段6评估不完整：缺补充统计记录，工时/成本类指标待统计"
  ],
  "test_scope": "full | partial | not_executed",
  "eval_scope": "complete | partial",
  "resume": { "resumable": false, "from_stage": null, "reason": null }
}
```

`completion_caveats` 按实际填写，不适用时删除对应条目：

- 使用过模拟回答/模拟裁决：保留“阶段1含模拟回答，非客户正式确认”，并逐条追加阶段2~4 的模拟项（如“S2-04 载流量与电流为保守模拟取值”“N 条强条为模拟预判，原表仍为待人工判定”“DB/FB 契约为模拟草案”）；
- `compile_checked`：保留“编译通过仅代表语法/接口，逻辑未验证”；
- `source_only`：替换为“编译未执行；源码已生成，语法/接口与逻辑均未验证”；
- `test_scope=partial`：追加“阶段5有 N 条用例未执行，通过率分母含/不含未执行已写明”；
- `test_scope=not_executed`：追加“阶段5仿真未执行：测试用例与追溯矩阵已生成，结果未采集”；
- `eval_scope=partial`：追加“阶段6评估不完整：<缺哪个输入/哪类指标待统计>”。

最终用户报告必须包含：

- flow_id、开始/结束时间、总耗时；
- 六阶段状态表（模拟项所在阶段标注 `通过（模拟）`；阶段5 标注 `通过（未执行）` 或 `未测试`；阶段6 标注 `评估不完整`）；
- 全部交付物路径（含阶段5 三件套、阶段6 三件套）；
- 模拟回答披露（如适用）；
- **“待复核（模拟）清单”**：按阶段列出每一个模拟裁决（对象、缺什么、取了什么、依据、风险、怎么复核）；
- 编译状态与验证范围、仿真执行状态与通过率分母口径、评估完整性（14 项指标中 `已计算`/`待统计` 各多少）；
- 未验证/待人工事项；
- `flow_status.json` 与 `flow_shturl` 路径。

禁止把 `source_only` 写成“编译通过”，禁止把模拟回答写成“客户已确认”，禁止把 `通过（模拟）` 写成“已验证/合规”，禁止把 `未执行` 写成“通过”，禁止把 `评估不完整` 写成“验收通过/项目合格”。

### 14.1 模拟模式下的交付定位

`auto_simulate_customer=true` 跑出的整套交付物定位为**可行性草案**，报告开头必须出现这句：

```text
本套交付物含 N 处模拟裁决，仅用于打通流程与形成草案；未经人工复核，不得作为设计、施工、采购或验收依据。
```

阶段5 为 `+untested` 或阶段6 为 `+eval_partial` 时，报告开头还需追加对应一句：

```text
仿真未执行：测试用例与追溯矩阵为设计成果，判定结果未采集，不得作为验证通过依据。
```

```text
评估不完整：部分指标待统计，结论只表示“已评估部分”，不代表项目合格。
```

`auto_simulate_customer=false` 时不出现第一句；后两句按实际状态出现。

---

## 15. 失败分类与终止行为

### 15.1 错误对象格式

```json
{
  "code": "E14_TEST_FAILED",
  "stage": 5,
  "message": "阶段5存在失败用例：TEST-002-01 期望 IO-010=1 实际 0",
  "evidence": ["./output/results.xlsx#02-问题定位", "./output/_stage5/sim_run.json"],
  "artifacts": ["./output/test_steps.csv", "./output/results.xlsx", "./output/traceability_matrix.xlsx"],
  "next_action": "按问题定位清单的归属阶段修复后从阶段N续跑；编排层不代为修改"
}
```

### 15.2 错误码

| 错误码 | 阶段 | 条件 | 顶层状态 |
|---|---|---|---|
| `E00_PREFLIGHT` | 0 | 输出目录/可写性/初始化失败 | `failed` |
| `E00_INVALID_PARAM` | 0 | 布尔参数/路径/`sim_channel` 非法 | `failed` |
| `E00_STATUS_WRITE` | 任意 | 状态文件写入或解析失败 | `failed` |
| `E01_MISSING_CUSTOMER_TEXT` | 1 | 客户原始文本为空 | `failed` |
| `E01_MISSING_PARAM` | 1 | 子技能返回 `【缺少参数：...】` | `failed` |
| `E02_SPEC_INVALID` | 1 | xlsx 不存在/表头/ID/状态/数据行不合格 | `failed` |
| `E02_VAGUE_ACCEPTANCE` | 1 | 验收准则含模糊词 | `failed` |
| `E02_UNRESOLVED_REQ` | 1 | 模拟模式下仍有 `待澄清` | `failed` |
| `E02_UNRESOLVED_CONFLICT` | 1 | 冲突未裁决 | `blocked` |
| `E03_PREV_STAGE` | 2 | 阶段1未成功 | `failed` |
| `E03_REQ_SPEC_INVALID` | 2 | 需求规格表缺失/无效 | `failed` |
| `E03_DEVICE_LIB_MISSING` | 2 | 器件库缺失/不可读 | `failed` |
| `E04_SELF_CHECK_FAILED` | 2 | 自检不通过 | `failed` |
| `E04_SELF_CHECK_UNDETERMINED` | 2 | 自检无法判定/待人工 | `blocked` |
| `E04_SELF_CHECK_UNREADABLE` | 2 | 自检报告缺失/无结论 | `failed` |
| `E05_PREV_STAGE` | 3 | 阶段2未成功 | `failed` |
| `E05_IO_LIST_MISSING` | 3 | `io_list.xlsx` 缺失/无效 | `failed` |
| `E05_BOM_MISSING` | 3 | `bom.xlsx` 缺失/无效 | `failed` |
| `E05_CLAUSE_LIB_MISSING` | 3 | 强条库缺失/不可读 | `failed` |
| `E06_OUTPUT_INVALID` | 3 | 交付物缺失/表头/重复ID/JSON无效 | `failed` |
| `E06_CLAUSE_FAILED` | 3 | 强条 `不满足` | `failed` |
| `E06_CLAUSE_UNDETERMINED` | 3 | 强条 `待人工判定`/`适用性待确认` | `blocked` |
| `E06_CLAUSE_UNREADABLE` | 3 | 强条表缺失/无结论 | `failed` |
| `E07_PREV_STAGE` | 4 | 阶段3未成功 | `failed` |
| `E07_IO_ADDRESS_MISSING` | 4 | `io_address.xlsx` 缺失/无效 | `failed` |
| `E07_DB_CONTRACT_MISSING` | 4 | DB/接口契约路径缺失或不存在 | `blocked` |
| `E07_PROJECT_MISSING` | 4 | 无可用 TIA 项目（未 OpenProject/Attach），无法读取真实 CPU/tag/DB | `blocked` |
| `E08_ENCODING_MOJIBAKE` | 4 | 导入后回读中文注释出现 GBK 误解码或与源文不一致 | `failed` |
| `E08_COMPILE_FAILED` | 4 | 编译失败/超3轮/残余错误 | `failed` |
| `E08_COMPILE_BLOCKED` | 4 | 编译待人工/阻塞 | `blocked` |
| `E08_COMPILE_STATUS_UNREADABLE` | 4 | 编译最终结论无法判定 | `failed` |
| `E08_NO_PROGRESS` | 4 | 同一编译错误连续两轮未消失（无进展） | `failed` |
| `E09_NO_SCL` | 4 | `src/` 无 `.scl` 或为空 | `failed` |
| `E09_LOG_MISSING` | 4 | `compilation_fix_shturl` 缺失/为空 | `failed` |
| `E10_STALE_OUTPUT` | 1~6 | 阶段输出与基线相比未变化 | `failed` |
| `E11_SUBSKILL_MISSING` | 0/任意 | 子技能不可加载 | `failed` |
| `E12_INTERRUPTED` | 任意 | 运行中断 | `interrupted` |
| `E13_ARTIFACT_CHANGED` | 续跑 | 已成功阶段产物哈希变化 | `failed` |
| `E14_PREV_STAGE` | 5 | 阶段4未成功 | `failed` |
| `E14_REQ_SPEC_INVALID` | 5 | 需求规格表缺失/表头/ID/无纳入需求 | `failed` |
| `E14_SSOT_INVALID` | 5 | `drawing_data.json` 缺失/结构异常/`traceability` 为空 | `failed` |
| `E14_COMPILE_LOG_INVALID` | 5 | 编译日志缺失/最终结论不可判定 | `failed` |
| `E14_SOURCE_MISSING` | 5 | `src/` 无 `.scl` 或为空 | `failed` |
| `E14_OUTPUT_MISSING` | 5 | 三件套缺失/为空/过期 | `failed` |
| `E14_CSV_INVALID` | 5 | `test_steps.csv` 表头/ID/场景/保持时间/点位引用不合格 | `failed` |
| `E14_RESULTS_INVALID` | 5 | `results.xlsx` 表头/判定词/用例集合/分母口径不合格 | `failed` |
| `E14_NOTE_MISSING` | 5 | `未执行`/`失败`/`阻塞` 行缺原因或证据 | `failed` |
| `E14_TRACE_INVALID` | 5 | 矩阵表头/TRACE-ID/链路完整性/N-A依据不合格 | `failed` |
| `E14_TRACE_UNREADABLE` | 5 | 覆盖率字段缺失/非数值 | `failed` |
| `E14_TRACE_COVERAGE_LOW` | 5 | 综合追溯覆盖率 < 100% | `failed` |
| `E14_TRACE_INCONSISTENT` | 5 | 覆盖率与矩阵行数矛盾（声称100%但有`部分`行） | `failed` |
| `E14_TEST_FAILED` | 5 | 存在 `失败` 用例 | `failed` |
| `E14_TEST_BLOCKED` | 5 | 存在 `阻塞` 用例 | `blocked` |
| `E14_SIM_NOT_EXECUTED` | 5 | 全部 `未执行` 且 `allow_untested_sim=false` | `blocked` |
| `E14_SCENE_MISSING` | 5 | 四类工况未覆盖且无 `不适用` 依据 | `failed` |
| `E14_SELFCHECK_FAIL` | 5 | `validate_stage5.py` 返回 `FAIL` 或无法运行 | `failed` |
| `E15_PREV_STAGE` | 6 | 阶段5未成功 | `failed` |
| `E15_OUTPUT_MISSING` | 6 | 三件套缺失/为空/过期 | `failed` |
| `E15_SHEET_MISSING` | 6 | `quality_metrics_summary.xlsx` 缺 5 张表之一 | `failed` |
| `E15_METRIC_MISSING` | 6 | `M-01`~`M-14` 不全 | `failed` |
| `E15_EVAL_UNREADABLE` | 6 | `eval_data.json` 缺失/损坏/指纹与报告不符 | `failed` |
| `E15_CLAIM_INVALID` | 6 | 结论词非法，或出现 `验收通过/项目合格/安全合规` 等表述 | `failed` |
| `E15_ARCHIVE_INCOMPLETE` | 6 | 归档缺项但未列缺失项/未写补齐指引 | `failed` |
| `E15_EVAL_INCONSISTENT` | 6 | 报告与台账数值/`待统计` 数/状态词不一致 | `failed` |

### 15.3 终止动作

任一阶段失败/阻塞/等待客户，立即：

1. 停止调度，不得启动下一阶段；
2. 保留所有已生成文件，不删除、不改名、不覆盖；
3. 更新 `flow_status.json`：阶段状态、`ended_at`、`duration_sec`、`error`、`resume`，阶段5/6 另写 `test_scope`/`eval_scope`；
4. 追加 `GATE_FAIL`/`ABORT`/`BLOCKED`/`WAIT_CUSTOMER` 日志；
5. 输出用户报告，包含：当前阶段、错误码、原因、证据、已生成交付物、未执行阶段、修复/补充建议、续跑入口；
6. 不替客户/子技能做修复设计，不自动回退上游阶段重跑。

### 15.4 等待客户与阻塞的区别

- `waiting_customer`：阶段1在非模拟模式下提出澄清问题；客户回复后可继续，不算失败。
- `blocked`：需求冲突待裁决、强条待人工判定、DB/契约缺失、仿真通道缺失且不放行、存在 `阻塞` 用例等；必须由人提供决定/文件/环境，编排层不得自行选择。
- `failed`：明确不通过、文件无效、编译失败、测试失败、覆盖率不足、评估物证无效、输出缺失、过期输出等。

---

## 16. 断点续跑与幂等

### 16.1 新流程 `fresh`

1. 不删除已有阶段交付物；记录基线哈希。`flow_status.json` 按 5.2 重新初始化，`flow_shturl` 追加新的 flow_id 段，不覆盖历史日志。
2. 阶段结束后，按各阶段 `Gx-01` 的关键输出哈希规则判断；关键输出与基线完全相同，视为 `E10_STALE_OUTPUT`，终止。  
   - 理由：防止旧文件伪装成本次阶段产物。
3. 若子技能确实需要复用旧文件，必须由子技能在输出中明确说明并更新文件；编排层不替它决定。
4. 用户要求覆盖旧结果时，仍由子技能覆盖；编排层不直接删除/改写阶段文件。
5. 阶段5/6 产物覆盖重跑时，批次号必须升级（阶段5 批次写入 `00-说明`；阶段6 `eval_data.json` 指纹随数据变化），不得复用旧批次冒充本次结果。

### 16.2 续跑 `resume`

1. 读取已有 `./output/flow_status.json`，校验 `schema_version`、`flow_id`、`cwd`、`total_stages=6`。
2. 对已标记 `success` 的阶段，重新计算其输出哈希；与状态文件记录不一致 → `E13_ARTIFACT_CHANGED`，不得直接信任旧状态。
3. 找到第一个非 `success` 阶段：
   - `waiting_customer`：从阶段1重新进入，读取客户新回复；
   - `failed`/`blocked`：从该阶段重新进入；先校验输入，再调用子技能；
   - `running`/`interrupted`：从该阶段重新进入，日志标记 `RESUME`。
4. 已成功阶段不重复执行业务设计；若其输出被下游依赖，只读校验，不修改。
5. 续跑复用原 `flow_id`，在 `flow_shturl` 追加 `RESUME`，保留原历史。
6. 阶段5 续跑时若上游代码已变更：`compilation_fix_shturl` 与 `.scl` 哈希变化 → 阶段5 必须整体重跑（用例、结果、矩阵同批次），不得只改结果表。

### 16.3 幂等原则

- 同一阶段重复执行，不得产生不同的业务决策；由子技能保证；
- 编排层只保证：输入一致、门禁一致、状态可追溯；
- 不允许“重跑直到通过”；每次失败都必须记录原因，修复后从失败阶段续跑。

---

## 17. 文件校验方法

### 17.1 通用

- 使用 `pathlib.Path`；不要用字符串拼接路径。
- 文件存在且 `is_file()`；大小 `stat().st_size > 0`。
- 读取文本统一 UTF-8；遇到编码错误按 `E0x_UNREADABLE` 终止。
- 哈希使用 SHA-256，分块读取；记录到 `artifacts`。
- 不修改被校验文件；只读打开。

### 17.2 xlsx

使用 `openpyxl.load_workbook(path, read_only=True, data_only=True)`：

1. 捕获异常 → 文件无效；
2. 取第一个工作表或指定工作表（阶段5/6 必须按表名取，不按序号）；
3. 表头行必须是第一行；
4. 逐列比较字符串，去除首尾空白；
5. 至少一条数据行；不要求编排层做业务计算；
6. 只读关闭工作簿。

### 17.3 Markdown / JSON / SCL / CSV / 日志

- Markdown：非空；自检报告只解析最终结论段；不重写表格；阶段6 报告按小节标题定位结论词。
- JSON：`json.loads`；失败即无效；`eval_data.json` 另校验指纹段存在。
- SCL：只检查扩展名、数量、非空；不解析语法（语法由阶段4子技能负责）。
- CSV：用 `csv.reader` 解析（`encoding="utf-8-sig"`），不按逗号切分字符串；表头逐字比较；列数一致。
- 日志：读取文本；只认最终结论段；不把历史轮次当最终结论；`compilation_fix_shturl` 与 `flow_shturl` 均无扩展名，按文件全名定位。

### 17.4 哈希清单

完成或终止时，`artifacts` 至少包含（只收阶段交付物）：

- 阶段1：`requirements_spec.xlsx`、`clarification_shturl.md`；
- 阶段2：`scheme.md`、`io_list.xlsx`、`bom.xlsx`、`multi_check_report.md`；
- 阶段3：六个交付物；
- 阶段4：所有 `.scl`、`compilation_fix_shturl`；模拟模式下另加 `plc_tag_map.csv`，以及生成过的 `db_definitions.xlsx`、`interface_contract.md`（草案，标注为模拟交付物）；
- 阶段5：`test_steps.csv`、`results.xlsx`、`traceability_matrix.xlsx`（过程证据 `_stage5/` 不入哈希集，但覆盖率数值必须与 `00-说明` 一致）；
- 阶段6：`project_evaluation_report.md`、`quality_metrics_summary.xlsx`、`project_archive_list.md`（`_stage6/eval_data.json` 不进 `artifacts` 哈希集，其指纹写入报告附录 A，用于回指核对）；
- 控制文件：`flow_status.json`、`flow_shturl` 不放入 `artifacts` 的哈希校验集，避免状态文件自引用和日志追加导致 `E13` 误报；在日志中记录其路径、大小和最后写入时间。

---

## 18. 参考实现

以下代码仅用于状态/日志/文件校验的参考，不是阶段业务逻辑；执行环境可按可用库调整。不得用这段代码替代子技能。

```python
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

OUT = Path("./output")
STATUS = OUT / "flow_status.json"
LOG = OUT / "flow_shturl"


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def record(path: Path) -> dict:
    if not path.is_file():
        return {
            "path": str(path),
            "exists": False,
            "size_bytes": None,
            "sha256": None,
            "mtime": None,
        }
    st = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": st.st_size,
        "sha256": sha256_file(path),
        "mtime": dt.datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds"),
    }


def atomic_write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def append_log(event: str, where: str, message: str, **fields: object) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    suffix = " ".join(
        f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in fields.items()
    )
    line = f"[{now_iso()}] [{where}] [{event}] {message}"
    if suffix:
        line += " | " + suffix
    with LOG.open("a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")


def xlsx_headers(path: Path, sheet: str | int = 0) -> list[str]:
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[sheet] if isinstance(sheet, str) else wb.worksheets[sheet]
        row = next(ws.iter_rows(min_row=1, max_row=1))
        return ["" if c.value is None else str(c.value).strip() for c in row]
    finally:
        wb.close()


def csv_headers(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [c.strip() for c in next(csv.reader(f))]


def require_headers(actual: list[str], expected: list[str], what: str) -> None:
    if actual != expected:
        raise ValueError(f"header mismatch [{what}]: {actual!r} != {expected!r}")


def last_conclusion(text: str) -> str:
    # 只取最后一次出现的“最终结论/总体结论/自检结论/编译结论”之后的内容
    pattern = re.compile(r"(最终结论|总体结论|自检结论|编译结论)\s*[:：]\s*(.+)")
    matches = pattern.findall(text)
    return matches[-1][1].strip() if matches else ""


def changed(before: dict, after: dict) -> bool:
    if before.get("exists") != after.get("exists"):
        return True
    return before.get("sha256") != after.get("sha256")
```

阶段5/6 专用校验要点（编排层只读，不重算）：

```python
STAGE5_CSV = ["TEST-ID", "关联REQ-ID", "测试场景", "输入激励", "保持时间(ms)", "期望输出"]
STAGE5_RESULT = ["TEST-ID", "关联REQ-ID", "测试场景", "输入激励", "期望输出", "实际输出", "判定结果", "备注"]
STAGE5_TRACE = ["TRACE-ID", "REQ-ID", "IO-ID", "BOM-ID", "TERM-ID", "CODE-ID", "TEST-ID", "链路完整性", "备注"]
VERDICTS = {"通过", "失败", "未执行", "阻塞"}
SCENES = ("正常工况", "急停工况", "故障工况", "复位异常工况")
STAGE6_SHEETS = ["00-说明", "01-指标台账", "02-工时成本", "03-风险清单", "04-归档核对"]
STAGE6_METRICS = [f"M-{i:02d}" for i in range(1, 15)]
CLAIM_BAN = ("验收通过", "项目合格", "安全合规", "已验收", "全部合规")
```

使用约束：

- `append_log` 的 `event`/`where` 由本技能固定使用，不允许自由发挥；
- `last_conclusion` 只用于最终结论段，不用于历史轮次；
- 阶段5/6 的覆盖率、指标、成本数值一律读子技能产出，不在此重算；
- 任何校验异常都必须转为明确错误码，不得静默吞掉。

---

## 19. 禁止事项

1. **禁止跳阶段/逆序/并行**：不得在阶段1未通过时生成阶段2文件，不得先跑阶段4再补阶段3，不得跳过阶段5直接评估。
2. **禁止替子技能做业务决策**：不得补写需求、选型、分配地址、计算电缆、判定强条、编写/修复 SCL、设计用例、判定测试结果、计算指标、写评估结论。
3. **禁止修改子技能输出**：不得编辑、重排、格式化、修复、删除、重命名任何阶段交付物；阶段5/6 也不得回改阶段1~4 的任何文件。
4. **禁止用旧文件冒充新输出**：基线未变化即 `E10_STALE_OUTPUT`。
5. **禁止伪造门禁**：未执行的检查不能写“通过”；无编译通道不能写“编译通过”；无仿真通道不能写“测试通过”。
6. **禁止合并阶段**：不得把阶段2/3/4 合并成一次“顺便做完”，也不得把阶段5/6 合并成“跑完顺手评估一下”。
7. **禁止修改固定路径**：`./output/`、`flow_status.json`、`flow_shturl`、各阶段文件名不得改。
8. **禁止把模拟回答写成客户确认**：`【模拟回答】` 永远不是 `已确认`。
9. **禁止把 `待人工判定` 自动关闭**：强条、冲突、缺参必须由人处理。模拟模式只允许在报告中给出 `【模拟裁决】` 预判并让门禁判 `通过（模拟）`，**原表里的 `待人工判定` 必须原样保留**。
10. **禁止把“未验证”写成“已验证”**：编译通过仅语法/接口；逻辑未验证。
11. **禁止阶段5 造假**：`未执行` 不得计入通过；不得按代码推断填 `实际输出`；不得删除未覆盖的 REQ 行来凑 100% 覆盖率；不得把 `失败` 改判为 `通过`。
12. **禁止阶段6 造数**：不得估值、不得 0 填、不得把 `待统计` 写成 0 或“约等于”；不得把基线数据当本项目数据；不得把一次性投入摊进单项目成本。
13. **禁止越权结论**：不得出现 `验收通过`、`项目合格`、`安全合规`、`全部合规`；阶段6 结论只有 `评估完成`/`评估不完整`。
14. **禁止自动回退重跑**：测试失败只能定位 + 给归属阶段 + 给续跑入口，不得编排层自动改上游文件后重跑。

---

## 20. 执行前自检清单

> **附加强制项（2026-11-16）**：本清单之外还必须逐条满足附录 Z 的 G-01~G-04，任一条不满足不得声明本阶段完成。

在启动阶段1前，逐项确认：

- [ ] 已创建 `./output/`；
- [ ] `auto_simulate_customer` 已解析为布尔值，默认 `true`；
- [ ] `device_library_path`、`clause_library_path` 已记录（不要求阶段1存在）；
- [ ] `db_definition_path`、`fb_contract_path` 已记录；未提供时：`auto_simulate_customer=false` 则阶段4会阻塞、`true` 则阶段4生成契约草案，两种情况都不提前猜；
- [ ] `sim_channel` 已解析（`auto`/`plcsim`/`none`）；`allow_untested_sim` 已解析为布尔值；
- [ ] `stage6_stats_path` 已记录；缺失时已告知用户阶段6 会出 `待统计`；
- [ ] 六个子技能均可加载（`req-spec-01`、`scheme-io-bom-02`、`elec-construction-03`、`plc-scl-gen-04`、`sim-trace-05`、`eval-archive-06`）；
- [ ] `flow_status.json` 已按 5.2 初始化，`current_stage=0`、`total_stages=6`；
- [ ] `flow_shturl` 已写文件头、启动时间、全局参数；
- [ ] 已记录各预期输出的基线哈希（阶段1~6 全部交付物）；
- [ ] 已明确本次 `run_mode`。

每个阶段结束后自检：

- [ ] 阶段输出文件存在且非空；
- [ ] 表头/ID/JSON/日志结论已校验；
- [ ] 失败/阻塞/等待状态已写入 `flow_status.json`；
- [ ] 日志已追加，未覆盖历史；
- [ ] 未修改任何子技能输出；
- [ ] 未提前启动下一阶段。

阶段5结束后额外自检：

- [ ] `test_steps.csv` 6 列、`results.xlsx` 8 列、`traceability_matrix.xlsx` 9 列逐字匹配；
- [ ] 用例集合与结果集合一致，无孤儿行；
- [ ] `未执行`/`失败`/`阻塞` 行均有原因与证据；
- [ ] 综合追溯覆盖率已读取且与矩阵行数不矛盾；
- [ ] `test_scope` 已写入，且与 `completion_scope` 的 `+untested` 一致。

阶段6结束后额外自检：

- [ ] 5 张表齐全，`M-01`~`M-14` 齐全；
- [ ] 结论词为 `评估完成`/`评估不完整`，无禁用表述；
- [ ] 报告数值可回指 `eval_data.json`，指纹一致；
- [ ] 归档 17 项逐条核对，缺失项与补齐指引已列；
- [ ] `eval_scope` 已写入，且与 `+eval_partial` 一致。

---

## 21. 最小执行伪代码

```text
preflight:
  ensure ./output
  parse params; flow_id; check 6 skills
  baseline all expected outputs（阶段1~6）
  init flow_status.json (with baseline); init flow_shturl

for stage in [1, 2, 3, 4, 5, 6]:
  if previous stage != success: abort
  check stage inputs
  set stage running; log STAGE_START
  invoke exact subskill，context 必带 auto_simulate_customer
  if stage in (5, 6): context 另带 sim_channel / allow_untested_sim / stage6_stats_path
  if subskill returns 【缺少参数：...】:
      if auto_simulate_customer == true and stage <= 4: 由模拟裁决补齐后重新调用（记录 SIMULATE）
      else: fail; abort
  if stage 1 and auto_simulate_customer == false and questions:
      set waiting_customer; log WAIT_CUSTOMER; stop
  check stage outputs and gate
  if stage <= 4 and gate == indeterminate and auto_simulate_customer == true:
      mark 通过（模拟）; log SIMULATE; append caveat; continue
  else if gate fail: set failed/blocked; log GATE_FAIL/ABORT; stop
  if stage == 5: set test_scope; if test_scope != full: append +untested caveat
  if stage == 6: set eval_scope;  if eval_scope == partial: append +eval_partial caveat
  set success; record gate.checks[].simulated; log GATE_PASS

set completed; completion_scope(+simulated/+untested/+eval_partial 按实际); caveats
log COMPLETE
write final flow_status.json
report to user（含“待复核（模拟）清单”、未测试声明、评估不完整声明）
```

---

## 22. 交付完成后的用户报告模板

### 22.1 成功

```text
全流程完成
- flow_id:
- 总耗时:
- 阶段状态: 1 成功 / 2 成功 / 3 成功 / 4 成功 / 5 成功（<全部通过|部分未执行|未执行>）/ 6 成功（<评估完成|评估不完整>）
- 交付物:
  - 需求: ./output/requirements_spec.xlsx, ./output/clarification_shturl.md
  - 方案/IO/BOM: ./output/scheme.md, ./output/io_list.xlsx, ./output/bom.xlsx, ./output/multi_check_report.md
  - 电气: ./output/io_address.xlsx, ./output/loop_description.md, ./output/cable_schedule.xlsx, ./output/terminal_list.xlsx, ./output/clause_check.xlsx, ./output/drawing_data.json
  - 代码: ./output/src/*.scl, ./output/compilation_fix_shturl
  - 仿真/追溯: ./output/test_steps.csv, ./output/results.xlsx, ./output/traceability_matrix.xlsx
  - 评估/归档: ./output/project_evaluation_report.md, ./output/quality_metrics_summary.xlsx, ./output/project_archive_list.md
- 编译状态: <编译通过（仅语法/接口；逻辑未验证）| 编译未执行>
- 仿真状态: <N 条用例全部通过（综合追溯覆盖率 100%）| 部分未执行：<原因>| 未执行：<原因>>
- 评估状态: <14 项指标中已计算 X 项、待统计 Y 项；归档 17/17|归档 Z 项缺失>
- 模拟回答披露: <有/无；有则说明非客户正式确认>
- 状态/日志: ./output/flow_status.json, ./output/flow_shturl
- 未验证/待人工事项: <列出；无则写无>
```

### 22.2 终止

```text
流程终止
- flow_id:
- 当前阶段: 阶段N <名称>
- 错误码:
- 原因:
- 证据:
- 已生成交付物:
- 未执行阶段:
- 修复/补充建议: <只描述需要人或子技能处理的事项，不替其设计>
- 续跑方式: run_mode=resume，从阶段N继续
```

> 终止报告不得省略“未执行阶段”，不得把未执行写成“跳过”，不得把阻塞写成“完成”。

---

## 23. TIA MCP 工具契约与中文编码硬门禁（2026-11-15 实测，强制）

> 本节为强制条款，优先于前文任何“推测/惯例”写法。实测环境：TIA Portal V21 + TIA MCP 2.7.8，S7-1511 V2.9。

### 23.1 工具名契约（只允许真实名称）

| 动作 | 真实工具 | 禁止写法 |
|---|---|---|
| 连接/状态 | `Connect`、`GetState`、`GetProject` | `list_project_devices` |
| 打开项目 | `OpenProject`、`AttachToOpenProject` | 猜测路径 |
| 读工程树 | `GetProjectTree`、`GetDevices`、`GetSoftwareTree` | `list_plc_blocks` |
| 读块 | `GetBlocksWithHierarchy`、`GetBlocks`、`DescribeBlockLogic` | — |
| 读变量 | `GetPlcTags`、`GetPlcTagTables` | `list_tags` |
| 建块/导入 | `PlcBuildAndImport`、`ImportPlcExternalSource` + `GenerateBlocksFromExternalSource`、`ImportFromDocuments` | `create_fb`、`import_scl_source` |
| 变量表 | `ImportPlcTagTable`（导入阶段3 的 `plc_tag_map.csv` 映射）、`GetPlcTagTables` | `create_tags`、手写变量表 |
| 编译 | `CompileAndDiagnosePlc`、`CompileSoftware` | `compile`、`get_compile_diagnostics` |
| 导出 | `ExportAsDocuments`、`ExportBlock` | `export_block` |
| 下载/在线 | `DownloadToPlc`、`GoOnline`、`GoOffline` | — |
| 读写值 | `SetWatchTableModifyValue`、`ReadPlcLiveValuesS7`、`ReadPlcWatchTableCurrentValuesReadOnly` | — |
| 保存 | `SaveProject` | — |
| 归档 | `ArchiveProject`（须先 `SaveProject`） | `archive_project` |

工具清单只列 65/238；**没看到不等于没有**——先 `FindTools("<能力描述>")`，再 `CallTool(name, argumentsJson)`。禁止臆造工具名。

### 23.2 中文注释硬门禁（ENC-01 ~ ENC-06）

- **ENC-01 编码**：`.scl` 外部源与 `.s7dcl` / `.s7res` 一律 **UTF-8 带 BOM（EF BB BF）**。实测无 BOM 时，变量注释与块体注释双双变成 `涓枃鍙橀噺娉ㄩ噴` 类乱码。
- **ENC-02 标题**：块标题/网络标题 **禁止中文**（实测会导致导入失败或 0 块）；标题 ASCII，中文只放注释。
- **ENC-03 位置**：变量注释写在声明同一行 `// 中文`（进 `.s7res` 的 `zh-CN` MLC）；块体注释写在 `BEGIN` / `NETWORK` 内。
- **ENC-04 回读**：每次导入后必须 `ExportAsDocuments` 回读，逐字比对中文；出现 `涓/锛/鍙/鏂/鐨` 等特征或与源文不一致 → `E08_ENCODING_MOJIBAKE`，禁止交付。
- **ENC-05 覆盖**：`GenerateBlocksFromExternalSource` **不覆盖**旧块，改块前必须 `DeletePlcBlock`；否则“编译 0 错误”不代表新逻辑已落地。
- **ENC-06 落盘**：任何写入后必须 `SaveProject`，否则重启即丢。

### 23.3 阶段0 能力探测

阶段0 必须调用 `Bootstrap` + `GetState` + `GetProject`，把结果写入 `./output/_stage0/capabilities.json`：

```json
{
  "mcpReady": true, "tiaVersion": 21, "connected": true,
  "openProject": null, "plcsimRunning": false,
  "toolLayer": "lite", "toolCount": 238,
  "encodingRule": "utf-8-bom", "titlesAsciiOnly": true
}
```

阶段1~6 只读该文件判断通道，不得各自猜测。

### 23.4 阶段4 启动条件（补充）

- 必须先 `OpenProject` / `AttachToOpenProject` 并 `GetProjectTree`；无项目 → `E07_PROJECT_MISSING`（`blocked`），不再“生成契约草案继续”。
- `softwarePath` 是 PLC **软件名**（如 `PLC_1`），不是设备名。
- 编译结论只认 `CompileAndDiagnosePlc` 的 `state`；`Success` 才可写“编译通过（仅语法/接口，逻辑未验证）”。

### 23.5 阶段5 执行前置（补充）

- “编译未执行”不是失败：三件套照出、判定全 `未执行`、`completion_scope` 追加 `+untested`。
- 真执行只允许 PLCSIM 目标；`DownloadToPlc` 前必须有人确认，禁止真机。
- `未执行` 与 `通过（模拟）` 是两种不同降级，报告中不得混写。

---

## 附录 Z：实机回归失败模式与强制检查

> 来源：2026-11-16 首次在 PLCSIM Advanced 上真实执行 81 条用例（不是设计推演；项目与设备信息已脱敏），
> 结果 56 通过 / 25 不符。以下每条都由**真实失败**反推，不是假设。
> 编号规则在各技能内唯一，交付前逐条打勾；任一条不满足不得声明阶段完成。
>
> **2026-11-16 修订（重要）**：Z.1 冒烟执行已改归阶段5（见 §12.3 G5-06 规则 5），Z.2 已并入 §12.3 G5-06"全部未执行"行，Z.4 的 `deviation` 已并入 §5.1 状态枚举。本附录保留背景与案例；**与正文冲突时以正文为准**。

### Z.1 冒烟执行归属（G-01 · 已并入 §12.3，不在阶段4 执行）

原写法"阶段4 通过条件增加：用阶段5 用例真实执行 ≥3 条"与流程顺序冲突（阶段5 用例此时尚未生成，且 §4 禁止逆序/预跑），也与 04 的红线"不仿真、不调试"冲突。现归属如下，**以本段为准**：

1. 阶段4 只做编译闭环，结束时 `completion_scope` 一律追加 `+logic_unverified`，并不得宣称"程序可用"。
2. 阶段5 生成全量用例后，优先生成并执行 3 条最小冒烟（1 正常流程 + 1 急停 + 1 复位），结果写入 `results.xlsx`。
3. 编排层在 G4 只记录 `+logic_unverified`，不校验执行；G5 按 §12.3 G5-06 规则 5 校验冒烟是否清除。
4. 未清除时，`+logic_unverified` 保留到最终报告，并在"未验证/待人工事项"里写明缺哪类场景。

> 背景：该项目阶段4 编译 0 error/1 warning 即放行，直到真实执行才发现 25 条用例不符。

### Z.2 执行覆盖率与"全未执行"（G-02 · 已并入 §12.3 G5-06）

与正文一致的口径（不要另立一套）：

1. `results.xlsx` 全为 `未执行` 时，`test_scope=not_executed`，**只有**在 `00-说明` 给出每个候选通道的具体失败证据（端口探测、实例状态、API 报错原文）时，才允许判 `success` + `+untested`；证据缺失即 `E14_SIM_NOT_EXECUTED`，阶段状态 `blocked`。
2. 至少 1 条真实执行（`通过`/`失败` 均可，`阻塞` 不算）时，按 §12.3 G5-06 的分布表判定。
3. 任何情况下都不得把 `未执行` 计入通过数、不得按代码推断判定。

### Z.3 阶段间回归（G-03 · 强制）

凡对已交付代码（`src/*.scl`）做修改，必须：改前归档 → 改后编译 → 重新下载 → 重跑受影响用例 → 记录前后对比。禁止"改完只编译就收工"。

> 本项目实测：同一套用例在 v2/v5/v6 三个工装版本下通过数 50/53/56，证明**工装与程序都会影响结论**，必须记录版本与对比。

### Z.4 交付物版本一致性（G-04 · 强制）

阶段6 完成后再发生任何上游修订，`flow_status.json` 必须登记为 `deviation` 或 `resume`，并刷新受影响产物哈希。禁止"改了数据但不改状态"。

### Z.5 门禁脚本（建议直接挂到 G4 / G5）

编排器在 G4、G5 门禁中应调用：

```bash
python <skills>/auto-flow-master-00/assets/checkers/check_stage4.py --project <项目根>
python <skills>/auto-flow-master-00/assets/checkers/check_stage5.py --project <项目根> --results output/results.xlsx
```

任一退出码为 `1`（FAIL）或 `2`（输入缺失）→ G4/G5 判 PASS 不成立，按附录 Z 的 G-01/G-02 降级处理并在
`flow_shturl` 记录 `GATE_FAIL`。两个脚本均**只读项目自有产物、不写死任何项目内容**，
换行业/换器件只改 `--profile`。两个脚本的首行均为 `PASS`/`FAIL`，末行仍保留明细摘要。
