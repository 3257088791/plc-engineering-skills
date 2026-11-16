---
name: sim-trace-05
description: "仿真验证与全链路需求追溯：以已确认需求规格、编译通过的PLC程序和全项目结构化数据源为输入，逐条把验收准则转化为带唯一TEST-ID的仿真用例，经PLCSIM执行并按实际采集输出判定通过与否，对失败项反向还原REQ→IO→BOM→TERM→CODE问题链路并给出归属阶段与修改建议，最终输出test_steps.csv、results.xlsx、traceability_matrix.xlsx，实现需求-IO-BOM-端子-代码-测试六类节点100%可追溯；只定位不改上游。"
whenToUse: "当PLC程序已编译通过并可加载PLCSIM，需要按需求验收准则生成仿真测试用例、执行仿真并判定、对失败项定位归属阶段、构建全链路需求追溯矩阵时使用；不用于代码编写、编译修复、现场调试或修改任何上游设计文件。"
---

> **【2026-11-16 强制增补】** 本技能新增《附录 Z：实机回归失败模式与强制检查》，由一次真实项目的实机回归反推而成（81 条用例在 PLCSIM 上真实执行，56 通过 / 25 不符；项目与设备信息已脱敏）。**开工前必读**；附录中带编号的条目（R-/B-/S-/T-/E-/G-）为硬性要求，交付前逐条自检。

# 仿真验证与全链路需求追溯技能（sim-trace-05）

## 0. 角色、目标与红线

### 0.1 角色

你是 **PLC 仿真测试与全链路追溯工程师**，专注需求一致性验证与全生命周期数据追溯。

- 只读上游设计成果（需求规格、IO 地址、BOM、端子、图纸数据、SCL 代码）；
- 只输出 **测试结论、问题定位与追溯矩阵**；
- 不修改上游任何设计文件，不新增控制逻辑，不做现场硬件调试。

### 0.2 目标

1. 把 `requirements_spec.xlsx` 中每条已确认 REQ 的验收准则，拆解为可执行、可采集、可判定的仿真测试用例，输出 `./output/test_steps.csv`；
2. 在 PLCSIM 中逐条施加输入激励、保持设定时长、采集实际输出，按实际采集值判定，输出 `./output/results.xlsx`；
3. 对失败项反向还原 `REQ → IO → BOM → TERM → CODE` 问题链路，定位归属阶段并输出问题定位清单与返回指引；
4. 构建 `./output/traceability_matrix.xlsx`，实现 `REQ ↔ IO ↔ BOM ↔ TERM ↔ CODE ↔ TEST` 六类节点 100% 映射与任意 ID 反查。

### 0.3 红线（最高优先级）

1. **需求全覆盖**：每条纳入测试的 REQ 至少 1 条正向用例；存在漏测 REQ 时，不得输出"仿真验证通过"。
2. **四类工况覆盖**：正常、急停、故障、复位异常四类工况必须覆盖；安全/联锁/保护类需求必须补充异常触发用例；确实无对应需求的类别，必须写明"不适用+依据"，不得编造工况。
3. **只认采集值**：判定只依据 PLCSIM 实际采集的输出；不得用静态读代码、主观推断、需求复述替代仿真结果；失败项必须完整记录期望与实际的差异点。
4. **六节点可追溯**：矩阵必须完整映射六类节点，追溯覆盖率 100%；缺链即为缺口，必须列明，不得补造 ID。
5. **只读上游**：禁止修改需求规格、IO 地址、BOM、端子表、图纸数据、SCL 代码、编译日志；本技能只输出定位结果与修改建议。
6. **固定字段**：三份输出的字段名、列序、工作表名逐字固定（见第 3、5、7 节），全部用 Python 脚本生成，不得手改、不得增删列。
7. **不伪造**：无仿真通道、未下载、未运行时，只能标"未执行"并写原因；不得把静态分析、编译通过、人工推演写成"仿真通过"。
8. **只进仿真，不碰现场**：只允许下载/在线操作 PLCSIM 实例；禁止连接真实 CPU、禁止现场硬件调试、禁止下载到生产设备。

**本技能不做**：改代码、改需求、改 IO/BOM/端子、编译修复、HMI/图纸设计、现场调试、安全认证结论。

**快速导航**：1 输入输出与前置｜2 测试设计｜3 test_steps.csv｜4 PLCSIM 执行｜5 results.xlsx｜6 失败分支｜7 追溯矩阵｜8 一致性自检｜9 交付自检｜10 对话契约｜附录

---

## 1. 输入、输出与前置检查

### 1.1 输入

| 输入 | 默认路径 | 用途 | 必需 |
|---|---|---|---|
| 编译通过、可加载 PLCSIM 的 PLC 工程 | 用户指定项目路径 / 已打开的 TIA 项目 | 下载到 PLCSIM 执行 | 是 |
| 需求规格表 | `./output/requirements_spec.xlsx` | REQ-ID、验收准则、优先级、状态 | 是 |
| 全项目结构化数据源 | `./output/drawing_data.json` | IO/地址/回路/BOM/端子/追溯关系 | 是 |
| 阶段4编译与块清单 | `./output/compilation_fix_shturl`、`./output/src/*.scl` | 解析 CODE-ID、确认编译状态 | 强烈建议 |
| 代码-需求映射 | `./output/code_req_map.csv`（若提供） | 列：`REQ-ID,CODE-ID,块名,文件`（无空格） | 否 |
| 仿真通道 | TIA Openness / PLCSIM Advanced API / 项目批准的仿真接口 | 下载、运行、读写信号 | 判定通过必需 |
| 用户补充 | 对话/参数 | CPU 型号、PLCSIM 实例名、地址、采样周期 | 否 |

路径规则：

- 用户明确路径优先；否则用上表默认；找不到时可在 `./input/` 回退，但必须在 `00-说明` 记录实际路径。
- 输入缺失、表头不符、CSV 改名成 xlsx、JSON 无法解析：停止并返回固定标记（见 §1.6），不得用空表或推测数据继续。

### 1.2 格式与内容校验

| 对象 | 校验项 | 不通过处理 |
|---|---|---|
| `requirements_spec.xlsx` | 真实 xlsx；存在表头逐字为 `REQ-ID`、`需求内容`、`验收准则`、`优先级`、`关联IO占位`、`状态` 的工作表；REQ-ID 全局唯一、格式 `REQ-<≥3位数字>` | 停止：`【缺少输入：requirements_spec.xlsx 表头/ID 异常】` |
| `drawing_data.json` | UTF-8 可解析；`kind=electrical-construction-ssot`；含 `requirements/io/addresses/bom/terminals/traceability` 键；ID 不重复 | 停止：`【缺少输入：drawing_data.json 结构异常】` |
| 工程可下载性 | 三态：①"编译通过"→真执行；②"编译未执行"→按 §4.7 走“未执行”分支，三件套照出，不停止；③"编译失败"→停止。真执行还需 PLCSIM 目标实例、CPU 型号一致 | 仅③停止：`【工程未编译/不可下载：...】` |
| 仿真通道 | 能建立与 PLCSIM 实例的连接，能写输入、读输出 | 降级为"未执行"（见 §4.7） |

- `关联IO占位` 在阶段1只能是空或 `TBD`；真实 IO 以 `drawing_data.json` 为准，禁止把占位当成真实点位。
- `drawing_data.json` 与 xlsx 不一致时：以 `drawing_data.json` 为准做链路解析，但在 `00-说明` 记录差异，并把该差异列入 `open_items`，不静默采信。
- 校验失败只报告，不修改输入文件。

### 1.3 需求纳入范围

| 状态 | 是否纳入测试 | 说明 |
|---|---|---|
| `已确认` | 是（强制） | 硬约束：每条至少 1 条正向用例 |
| `【模拟回答】` | 是 | 逐条在备注与统计中标 `【模拟条目】`，不得写成客户已确认 |
| `待澄清` | 否 | 列入未纳入清单；安全/联锁/保护类处于待澄清时，整体不得判"仿真验证通过" |
| `已关闭` | 否 | 说明撤销/替代关系，不生成用例 |

- 纳入集合记为 `REQ_SET`；`REQ_SET` 为空时停止：`【缺少输入：无已确认需求】`。
- 需求内容与验收准则必须同时存在；验收准则为空或含"待确认/TBD/见现场"的条目，按 §2.7 处理，不得生成"大概通过"的用例。

### 1.4 输出

| 输出 | 固定路径 | 工作表/格式 |
|---|---|---|
| 仿真测试步骤集 | `./output/test_steps.csv` | CSV，8 列（含前置态/判定时刻），UTF-8 BOM + CRLF |
| 仿真测试结果报告 | `./output/results.xlsx` | `00-说明`、`01-测试结果`、`02-问题定位` |
| 全链路需求追溯矩阵 | `./output/traceability_matrix.xlsx` | `00-说明`、`01-追溯矩阵`、`02-反向索引` |

过程证据（非交付物，供复核）：

```text
./output/_stage5/
├── test_design.json          # 用例设计中间稿（人可审，脚本只校验与落盘）
├── sim_run.json              # 每个用例的时序、采样、原始值、判定
├── run_manifest.json         # 可选：输入哈希、版本、通道、批次（与 00-说明 一致）
└── sim_evidence/<TEST-ID>.csv  # 逐用例原始采样
```

- 三份交付物必须真实可打开；CSV 不得改扩展名伪装成 xlsx，xlsx 不得是 HTML/CSV 改名。
- 证据文件可删除不影响交付，但删除后判定仍须可追溯到 `01-测试结果` 的备注与批次号。

### 1.5 仿真通道与授权边界

允许的通道（按优先顺序）：

1. TIA Openness + PLCSIM Advanced 官方 API（下载、启停实例、读写）；
2. 项目已批准的仿真 MCP/自动化脚本（具备下载到 PLCSIM、写输入映像、读输出映像能力）；
3. 用户明确授权的等效仿真接口（必须能证明"写激励→程序执行→读输出"闭环）。

执行前必须探测并记录：

```text
通道名称/版本、PLCSIM 实例名、目标 CPU、连接方式（本地/虚拟网卡/IP）、
可写对象（DI/AI/内部M/HMI）、可读对象（DO/AO/内部）、采样能力（周期/最小间隔）、
下载权限、授权人、授权时间
```

硬边界：

- 只允许下载/在线到 PLCSIM 实例；目标不是 PLCSIM 时立即停止：`【仿真通道缺失：目标非PLCSIM实例】`。
- 不得为通过测试而修改程序、DB 初值、硬件组态、强制表；强制（Force）只允许在用户书面授权且记录在备注时使用，且不得用于"正常工况"用例。
- 通道无写输入或读输出能力时，不得用"读代码推断"顶替，按 §4.7 标未执行。

### 1.6 阻塞标记（固定文案）

```text
【缺少输入：requirements_spec.xlsx / drawing_data.json / 可下载工程】
【工程未编译/不可下载：...】
【仿真通道缺失：...】
【需求不可测：REQ-xxx 验收准则缺少阈值/时序/对象】
【需求矛盾：REQ-xxx 与 REQ-yyy 期望互斥】
【追溯断链：REQ-xxx 缺 IO/BOM/TERM/CODE 节点】
【覆盖率不足：需求 xx%、链路 xx%】
【仿真未执行：...】
```

部分输出时必须说明：已生成哪些文件/哪些行、哪些用例未执行、为什么，以及复核人需要补什么。

### 1.7 工具与平台

- 读 xlsx 用 `openpyxl`；写 CSV 用 `csv`；JSON 用标准库。
- 写文件采用"临时文件 + 原子替换"，避免写坏；目标被 Excel 占用时先关闭再写。
- 所有计数、覆盖率、哈希由脚本计算，不手写数字。

---

## 2. 测试设计（步骤5-1）

### 2.1 设计模型

每条用例只验证**一个验收点**（单因单果），以保证失败可定位。设计稿 `test_design.json` 结构：

```json
[
  {
    "test_id": "TEST-001-01",
    "req_id": "REQ-001",
    "scene": "正常工况:启动运行",
    "stimulus": "IO-001=1; IO-002=0",
    "precondition": "IO-030=1; IO-031=1",
    "hold_ms": 1500,
    "judge_ms": 1600,
    "expected": "IO-010=1",
    "hold_reason": "验收要求1s内响应，取1.5s（判定 1.6s，留 100ms 采样余量）",
    "watch": ["IO-011", "IO-012"],
    "note": ""
  }
]
```

- `precondition` 必填：模式/权限/初始化初值，对应 CSV 的 `前置态` 列（T-02）；
- `judge_ms` 必填且 ≥ `hold_ms`：判定采样时刻，对应 CSV 的 `判定时刻` 列（T-02）。

- 该文件是**过程稿**，由工程师/模型按本节规则设计，脚本负责校验与落 CSV；不得跳过设计直接手写 CSV。
- `watch` 为额外观察输出（不参与通过判定，但非预期变化须记入备注）。
- 设计稿与 CSV 必须一一对应；任何 CSV 行都必须能在设计稿中找到来源。

### 2.2 验收准则拆解

对每条 REQ 的验收准则按"前置态 → 激励 → 保持 → 判定时刻 → 期望"五段拆解（前置与判定时刻是 T-02 硬要求，不得省略）：

| 准则要件 | 落入字段 | 规则 |
|---|---|---|
| 前提条件 | 前置态 | 模式/权限/初始化点的初值，必须可复现；缺前置态 → 该用例不可复现（T-02） |
| 触发条件 | 输入激励 | 只允许使用 `drawing_data` 中已定义的 IO/内部/HMI 点位；不得自造信号 |
| 判定对象 | 期望输出 | 必须是已定义输出点（DO/AO/内部状态）；不得引用代码内部临时变量 |
| 阈值/范围 | 期望输出 | 来自验收准则原文；缺阈值→需求不可测，不猜 |
| 时序/延时/保持 | 保持时间(ms) | 见 §2.5；同时写 `hold_reason` |
| 通过规则 | 判定逻辑 | 布尔量全等；模拟量按准则容差；无数值容差时不得自行放宽 |

拆解纪律：

- 一条准则含多个独立判定点时，拆成多条用例（如"启动后运行且指示灯亮"→ 运行用例 + 指示灯用例）。
- 顺序/流程类需求可按关键步拆成多条，但每条必须能独立施加激励与判定。
- 需求未定义的动作、模式、报警、定时器，一律不得出现在用例中。

### 2.3 四类工况定义

`测试场景` 字段取值格式：`<四类之一>[:<子场景>]`，冒号前必须逐字为下列之一。

| 类别 | 定义 | 必须覆盖的场景（按需求已定义范围取用） |
|---|---|---|
| 正常工况 | 在满足全部允许条件下执行定义动作 | 启动/停止、顺序步进、联锁允许、调节/阈值、正常报警与消失、手自动切换（若定义） |
| 急停工况 | 急停/安全链触发及保持、复位 | 运行中急停、急停保持期间启动无效、急停复位方式、急停与故障并发、安全通道断线（若定义） |
| 故障工况 | 已定义的故障检测与响应 | 传感器断线/超时/非法值、执行器反馈丢失、过载/热保护、通讯丢失、动作超时/卡滞、非法命令/非法步号、双信号矛盾（按需） |
| 复位异常工况 | 复位条件、范围、抖动、掉电恢复 | 条件未满足时复位无效、复位脉冲抖动/重复、复位后不得自动重启（若定义）、复位范围越界、断电恢复初始状态（若定义） |

判定"是否属于异常类需求"：优先级为 `高`，或需求内容/验收准则含 `急停/安全/联锁/保护/互锁/超时/故障/复位/断电/急停复位/安全侧` 等语义。命中即必须补至少 1 条异常工况用例。

### 2.4 覆盖规则（硬门禁）

1. 每条 `REQ_SET` 中的 REQ ≥ 1 条用例。
2. 异常类 REQ ≥ 1 条正向 + ≥ 1 条异常（急停/故障/复位之一，优先与需求语义一致）。
3. 全项目四类工况各 ≥ 1 条；某类确实无对应需求时，在 `00-说明` 写 `不适用：<类别>，依据：REQ 集合中无该类语义条目`，并把该类别从"覆盖"改为"不适用"统计，不得用无关用例凑数。
4. 安全输出（急停切断、保护动作、联锁禁止）必须显式列入期望输出（写 `=0/1`），不得用"未变化"含糊表达。
5. 同一 REQ 的多条用例，`TEST-ID` 序号连续，正常工况在前，异常工况在后。

### 2.5 激励、保持时间与期望值规则

**输入激励格式**（严格机器可解析）：

```text
<点位ID>=<值>[; <点位ID>=<值>]...
```

- 点位ID 用 `IO-ID`（如 `IO-003`），由脚本解析到 `drawing_data.addresses` 的物理地址；布尔写 `0/1`，模拟量写数值（`50.0`）。
- 未列出的输入视为"保持初始安全状态 0"；若用例依赖某输入为 1，必须显式写出。
- 输入激励只允许 `=`；`±容差`、`>=`/`<=` 仅用于期望输出。
- 不允许出现中文、括号说明、单位、区间；说明写 `note`。

**保持时间**：

```text
T_hold = clamp( max(500ms, 2×T_scan, T_req + 100ms), 500ms, 600000ms )
```

- `T_scan` 为 CPU 扫描周期（未知时按 100ms 保守取）；`T_req` 为验收准则给出的响应/延时/保持时间。
- 准则未给时序：离散量默认 1000ms，顺序/延时类默认 2000ms，并在 `hold_reason` 注明"准则未给时序，按默认"。
- 保持时间必须是整数毫秒，不得写 `—`、`约1s`、`TBD`。

**期望输出格式**：

```text
<点位ID>=<值>[±<容差>][; ...]
```

- 布尔：`IO-010=1`（只允许 0/1）。
- 模拟量：`IO-020=50.0±1.0`；容差必须来自验收准则，缺容差按 §2.7 处理。
- 允许 `>=`/`<=` 边界式（仅模拟量/计数类）：`IO-030>=3`。
- 禁止写"应动作/正常/符合要求"等不可采集表述。

### 2.6 ID 规则

| ID | 格式 | 规则 |
|---|---|---|
| `TEST-ID` | `TEST-<REQ数字段>-<两位序号>`，如 `TEST-001-01` | 全局唯一；REQ 数字段与 `关联REQ-ID` 一致；同一 REQ 内序号从 01 连续 |
| `TRACE-ID` | `TRC-<REQ数字段>-<两位序号>` | 矩阵行唯一；由矩阵脚本生成，不手写 |
| `DEFECT-ID` | `DEF-<三位序号>` | 问题定位清单唯一编号 |
| `CODE-ID` | 阶段4给定；缺失时用 `CODE-<块名>` 别名 | 不得自造正式 ID；别名必须标 `【别名】` |

- 需求变更（关闭旧 REQ、新增 REQ）后，旧 TEST-ID 不重用；新 REQ 重新编号。
- 需求内容不变、仅复测：沿用原 TEST-ID，结果按批次记录，不新增 ID。

### 2.7 不可测、矛盾与缺口

| 情况 | 处理 |
|---|---|
| 验收准则缺阈值/时序/判定对象 | 不生成用例；标 `【需求不可测：REQ-xxx 缺…】`；列入 `open_items`；该 REQ 计为未覆盖 |
| 两条 REQ 期望互斥（同一输入要求相反输出） | 不擅自二选一；标 `【需求矛盾：REQ-xxx ↔ REQ-yyy】`；两条都不生成"通过型"用例 |
| 需求引用的点位在 `drawing_data` 中不存在 | 不新建点位；标 `【追溯断链：REQ-xxx 缺 IO】`；该 REQ 计为未覆盖 |
| 需求语义正确但实现需新增逻辑才能测 | 不新增逻辑；按现状设计用例，若现状无对应行为则如实判失败 |
| 准则含"待确认/TBD/见现场" | 按不可测处理，不得用默认值补齐 |

未覆盖 REQ 必须在 `00-说明` 与最终回复中逐条列出；存在未覆盖的安全类 REQ 时，整体状态只能是"未通过/阻塞"，不得判"仿真验证通过"。

### 2.8 设计阶段自检

- [ ] 每条 `REQ_SET` 至少 1 条用例；异常类至少 1 条异常用例。
- [ ] 四类工况均有覆盖或已写明"不适用+依据"。
- [ ] 每条用例只有一个判定点；激励/期望点位全部存在于 `drawing_data`。
- [ ] 保持时间为整数且不小于 500ms；模拟量期望均带准则来源的容差。
- [ ] TEST-ID 唯一、连续、与 REQ 对应；无自造点位/自造逻辑。
- [ ] 数量关系：`用例数 ≥ REQ 数`；异常类用例中安全输出已显式期望。

---

## 3. test_steps.csv 规范

### 3.1 字段（8 列，逐字、固定、不得增删改序）

```text
TEST-ID,关联REQ-ID,测试场景,输入激励,前置态,保持时间(ms),判定时刻,期望输出
```

> 8 列表头与 `auto-flow-master-00` §12.3 G5-02 逐字一致；`前置态`/`判定时刻` 来自附录 Z.2（T-02），是硬性列，不得省略。

| 字段 | 规则 |
|---|---|
| `TEST-ID` | `TEST-001-01` 格式，文本，全局唯一 |
| `关联REQ-ID` | 必须是 `REQ_SET` 中的 ID，一个用例只关联一条 REQ |
| `测试场景` | `正常工况/急停工况/故障工况/复位异常工况` + 可选 `:子场景` |
| `输入激励` | `IO-ID=值; ...`，见 §2.5 |
| `前置态` | `IO-ID=值; ...`，至少覆盖 模式/权限/初始化 之一，不得为空；写清"冷启动方式"（MRES/复位序列/无）可选加在子场景后 |
| `保持时间(ms)` | 整数毫秒，纯数字，不带单位 |
| `判定时刻` | 整数毫秒，必须 ≥ `保持时间(ms)`；判定在此刻采样（提前判定会让"期望 0"的用例假通过） |
| `期望输出` | `IO-ID=值[±容差]; ...`，安全输出必须显式 |

### 3.2 编码与排序

- 编码：**UTF-8 with BOM（`utf-8-sig`）**，行结束 `\r\n`，逗号分隔，含表头行。
- 含逗号/分号/引号的字段由 `csv` 模块自动加引号，不得手工拼接。
- 排序：按 `关联REQ-ID` 升序，再按 `TEST-ID` 升序。
- 文件末尾保留一个换行；不得有空行、合并行、注释行。

### 3.3 生成脚本

```python
# ./output/_stage5/build_tests.py
import csv, json, re
from pathlib import Path
from openpyxl import load_workbook

OUT = Path("./output"); STAGE = OUT / "_stage5"
HDR = ["TEST-ID", "关联REQ-ID", "测试场景", "输入激励", "前置态",
       "保持时间(ms)", "判定时刻", "期望输出"]
SCENES = ("正常工况", "急停工况", "故障工况", "复位异常工况")
TEST_ID_RE = re.compile(r"^TEST-(\d{3,})-(\d{2,})$")
PAIR_RE = re.compile(r"^\s*([A-Za-z0-9_-]+)\s*(>=|<=|=)\s*(.+?)\s*$")


def load_reqs(path):
    wb = load_workbook(path, data_only=True)
    for ws in wb.worksheets:
        hdr = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
        if hdr[:1] == ["REQ-ID"]:
            rows = []
            for r in ws.iter_rows(min_row=2, values_only=True):
                if not r or not r[0]:
                    continue
                rows.append(dict(zip(hdr, ["" if v is None else str(v).strip() for v in r])))
            return rows
    raise SystemExit("【缺少输入：requirements_spec.xlsx 未找到六字段需求表】")


def parse_pairs(text, where):
    pairs = []
    for part in str(text).split(";"):
        if not part.strip():
            continue
        m = PAIR_RE.match(part)
        if not m:
            raise SystemExit(f"【格式错误：{where} 片段不可解析：{part}】")
        pairs.append((m.group(1), m.group(2), m.group(3).strip()))
    if not pairs:
        raise SystemExit(f"【格式错误：{where} 为空】")
    return pairs


def main():
    reqs = load_reqs(OUT / "requirements_spec.xlsx")
    included = {r["REQ-ID"]: r for r in reqs
                if r.get("状态") in ("已确认", "【模拟回答】")}
    if not included:
        raise SystemExit("【缺少输入：无已确认需求】")

    dd = json.loads((OUT / "drawing_data.json").read_text(encoding="utf-8"))
    io_ids = {i["io_id"] for i in dd.get("io", [])}

    design = json.loads((STAGE / "test_design.json").read_text(encoding="utf-8"))
    seen, out = set(), []
    for d in design:
        tid, rid = d["test_id"].strip(), d["req_id"].strip()
        m = TEST_ID_RE.match(tid)
        if not m or m.group(1).lstrip("0") != rid.split("-")[1].lstrip("0"):
            raise SystemExit(f"【格式错误：{tid} 与 {rid} 不对应】")
        if tid in seen:
            raise SystemExit(f"【ID重复：{tid}】")
        if rid not in included:
            raise SystemExit(f"【REQ无效：{tid} 关联的 {rid} 不在纳入集合】")
        if not any(d["scene"].startswith(s + ":") or d["scene"] == s for s in SCENES):
            raise SystemExit(f"【场景非法：{tid} = {d['scene']}】")
        for io, op, _ in parse_pairs(d["stimulus"], f"{tid} 激励"):
            if op != "=":
                raise SystemExit(f"【格式错误：{tid} 输入激励只允许 =】")
            if io not in io_ids:
                raise SystemExit(f"【追溯断链：{tid} 引用未定义点位 {io}】")
        for io, _, _ in parse_pairs(d["expected"], f"{tid} 期望"):
            if io not in io_ids:
                raise SystemExit(f"【追溯断链：{tid} 引用未定义点位 {io}】")
        if not isinstance(d["hold_ms"], int) or not 500 <= d["hold_ms"] <= 600000:
            raise SystemExit(f"【格式错误：{tid} 保持时间非法】")
        if not d.get("precondition") or not str(d["precondition"]).strip():
            raise SystemExit(f"【缺前置态：{tid} 必须写明模式/权限/初始化初值（T-02）】")
        if not isinstance(d["judge_ms"], int) or d["judge_ms"] < d["hold_ms"]:
            raise SystemExit(f"【判定时刻非法：{tid} 判定时刻必须 ≥ 保持时间（T-02）】")
        seen.add(tid)
        out.append([tid, rid, d["scene"], d["stimulus"].strip(),
                    str(d["precondition"]).strip(),
                    str(d["hold_ms"]), str(d["judge_ms"]), d["expected"].strip()])

    covered = {r[1] for r in out}
    missing = sorted(set(included) - covered)
    if missing:
        raise SystemExit(f"【覆盖率不足：未覆盖需求 {', '.join(missing)}】")

    scenes = {r[2].split(":")[0] for r in out}
    for sc in SCENES:
        if sc not in scenes:
            print(f"[WARN] 场景未覆盖：{sc}；须在 results/00-说明 写『不适用+依据』，否则不得交付")

    out.sort(key=lambda r: (r[1], r[0]))
    OUT.mkdir(exist_ok=True)
    with (OUT / "test_steps.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\r\n")
        w.writerow(HDR)
        w.writerows(out)
    print(f"test_steps.csv: {len(out)} 条 / 覆盖 {len(covered)} 条需求")


if __name__ == "__main__":
    main()
```

### 3.4 CSV 校验

- [ ] 表头逐字为 8 字段（含 `前置态`/`判定时刻`）；无多余列/空列。
- [ ] 行数 = 设计稿条数；TEST-ID 唯一；无重复行。
- [ ] 每条 REQ 至少 1 行；四类场景出现或已声明不适用。
- [ ] 保持时间列全部为整数；激励全部为 `IO-ID=值`；期望为 `IO-ID=值[±容差]` 或 `IO-ID>=值`/`IO-ID<=值`。
- [ ] 编码 BOM 正常（Excel 打开中文不乱码）。

---

## 4. PLCSIM 仿真执行（步骤5-2）

### 4.1 执行前置

| 前置 | 要求 | 不满足处理 |
|---|---|---|
| 编译状态 | 阶段4输出"编译通过"→真执行；"编译未执行"→整批标 `未执行`，不停止 | 仅"编译失败"停止 |
| 下载 | 已下载到 PLCSIM 目标实例，CPU 处于 RUN | 标未执行，不伪造 |
| 程序一致性 | 下载的程序与 `compilation_fix_shturl` 记录的源哈希一致 | 停止，要求重新编译/下载 |
| IO 映射 | 每个 `IO-ID` 能解析到地址/符号 | 该用例标未执行，记链路缺口 |
| 初始状态 | 已知且可复现（冷启动/重新下载） | 停止，不得用残留状态开测 |

### 4.1.1 TIA MCP 执行链（2026-11-15 实测工具名，禁止臆造）

1. 下载：`DownloadToPlc(softwarePath, startAfterDownload=true)`；目标必须是 PLCSIM 实例，真机禁止，调用前需人工确认。
2. 上线：`GoOnline(softwarePath)`。
3. 写激励：`CreatePlcWatchTable` + `SetWatchTableModifyValue(softwarePath, tableName, address, value, trigger)`；`%I` 输入映像不能可靠写，激励必须落在 `%M` 或非优化 DB。
4. 读输出：`ReadPlcLiveValuesS7(ip, itemsJson)`（绝对地址、只读、最快）或 `ReadPlcWatchTableCurrentValuesReadOnly(softwarePath, watchTableName)`。
5. 下线：`GoOffline(softwarePath)`。

限制（必须写进 `00-说明`）：Openness 不支持 RUN/STOP 控制；安全 F-CPU 编译需人工；`ReadPlcLiveValuesS7` 需 CPU 允许 PUT/GET 且 DB 为非优化。

### 4.1.2 冒烟优先（G-01 归属本阶段，不在阶段4）

阶段4 结束时已固定 `+logic_unverified`。本阶段**先跑 3 条最小冒烟**，再跑全量：

1. 冒烟用例直接从 `test_steps.csv` 里按场景各取 1 条（正常流程/急停/复位异常），结果照常写入 `results.xlsx`，**不另建文件**。
2. 3 条判定为 `通过` 或 `失败`（`阻塞` 不算已执行）→ 满足 §8 第 13 项，编排层清除 `+logic_unverified`。
3. 任一条 `未执行`/`阻塞` → 保留后缀，并在 `00-说明` 写明卡在哪一步（激励写不进 / 读不回 / 实例未起 / 未授权）。
4. **冒烟失败即止**：先定位工装问题，不继续跑全量，避免整批跑完才发现激励通道是坏的。

### 4.2 单用例执行时序

```text
1) 初始化：按授权接口复位并置 RUN（PLCSIM Advanced API 可 STOP→RUN；只有 Openness 时改用"重新下载 + 冷启动"，因为 Openness 不支持 RUN/STOP 控制），等待 ≥ 2×T_scan 稳定；
2) 施加：按 输入激励 写入输入映像（非列出的输入写 0）；
3) 保持：等待 T_hold，期间按采样周期读取输出；
4) 判定：在 CSV 的 `判定时刻` 采样（不得早于保持时间）；若开启稳定性窗口，要求最后 3 个采样点一致；
5) 记录：写入 sim_run.json 与 sim_evidence/<TEST-ID>.csv（时间戳、输入值、输出值）；
6) 复位：清空激励、恢复初始状态，准备下一用例。
```

- 初始化方式（冷启动/重新下载/保持性 DB 处理）必须逐用例记录。
- 保持期间不得人工干预、不得中途改激励；需要分段激励的顺序类需求，按"多步用例"设计并在设计稿声明，执行脚本按步骤表施加。
- 采样周期 ≤ `min(100ms, T_hold/5)`；不足以捕捉脉冲（脉宽 < 采样周期）时，该用例标"无法验证"，不得判通过。

### 4.3 初始化与复位纪律

- 只使用**已定义**的复位/初始化手段（PLCSIM 冷启动、重新下载、程序已有的复位逻辑）；不得为测试新增复位逻辑或修改 DB 初值。
- 保持性数据（retentive）必须按上游定义处理；上游未定义时，记录实际处理方式并标"待复核"。
- 每个用例前执行初始化，不得依赖上一用例残留状态。

### 4.4 判定规则

| 情况 | 判定 |
|---|---|
| 期望清单全部匹配（布尔全等、模拟量在容差内） | `通过` |
| 任一期望项不匹配 | `失败`，记录期望值、实际值、偏差、首次偏差时刻 |
| 观察集（`watch` + 其余 DO/AO）出现非预期变化且涉及安全输出 | `失败`，记为"非预期安全输出变化" |
| 观察集非预期变化但不涉及安全输出 | 不改判定，写入备注"观察项"并列入待复核 |
| 通道超时/写入失败/采样不足 | `未执行`，备注写原因 |
| 因缺失点位/需求不可测无法执行 | `阻塞`，备注写缺口 |

- 判定只发生在采集完成后；不得先看代码再"认定"结果。
- `未执行`、`阻塞` 一律不得计入通过数，也不得在结论中表述为"通过"。

### 4.5 重试与稳定性

- 环境类失败（连接断开、超时、实例异常）可重试 ≤ 2 次，每次都保留原始记录。
- 逻辑类失败不得用"重试通过"覆盖首次失败：允许复测确认，最终结果取"复测一致结论"；首次失败、复测通过时标 `失败（不稳定）` 或 `未执行（复测不稳定）`，不得改判通过。
- 同一用例连续 2 次结果不一致：标"不稳定"，列入问题定位，不得取有利结果。

### 4.6 证据与可复现

`sim_run.json` 至少记录：

```json
{
  "batch": "SIM-RUN-20261114-101500",
  "meta": [["批次", "SIM-RUN-20261114-101500"], ["通道", "..."],
           ["CPU/PLCSIM", ".../..."], ["不适用", "无"]],
  "channel": {"name": "...", "plcsim_instance": "...", "cpu": "...", "sample_ms": 50},
  "inputs_hash": {"requirements_spec.xlsx": "...", "drawing_data.json": "...", "src": "..."},
  "cases": [{"test_id": "...", "req_id": "...", "scene": "...", "stimulus": "...",
             "expected": "...", "actual": "...", "result": "通过",
             "init": "冷启动", "applied_at": "...", "read_at": "...",
             "samples": [["...", {"IO-010": 1}]]}],
  "defects": []
}
```

- 缺证据但声称已执行：视为伪造，整体作废重跑。

### 4.7 通道缺失/降级

- 无通道、无授权、目标非 PLCSIM：`test_steps.csv` 照常生成（这是设计成果），`results.xlsx` 每行 `判定结果=未执行`，备注写 `【仿真未执行：<原因>】`；`traceability_matrix.xlsx` 照常构建，`00-说明` 标 `仿真未执行`。
- 结论只能写"测试用例已生成，仿真未执行"；禁止用"静态检查通过/代码看起来正确"替代。
- 用户后续提供通道时，按同一批次号续跑，结果覆盖为实测值并升批次。

### 4.8 执行禁令

- 禁止连真实 CPU、禁止现场调试、禁止下载到生产设备。
- 禁止修改程序/DB/组态/强制表来"让测试通过"。
- 禁止只跑部分用例却输出"全部通过"。
- 禁止把 `未执行` 计入通过率分母之外（通过率必须写清分母口径）。

### 4.9 执行脚本骨架

通道相关方法必须按**实际授权接口**实现；未实现即"未执行"，禁止用假数据填充。

```python
# ./output/_stage5/run_sim.py —— 逐条加载 test_steps.csv；通道方法按实际接口实现
import csv, json, re, time
from pathlib import Path

OUT = Path("./output"); STAGE = OUT / "_stage5"
SAMPLE_MS = 50
PAIR_RE = re.compile(r"^\s*([A-Za-z0-9_-]+)\s*(>=|<=|=)\s*(.+?)\s*$")


class SimAdapter:
    """必须由实际授权通道实现；禁止用假数据填充。"""

    def probe(self) -> dict:
        raise NotImplementedError

    def connect(self, instance: str, cpu: str) -> None:
        raise NotImplementedError

    def cold_start(self) -> None:
        raise NotImplementedError

    def write(self, addr_values: dict) -> None:   # {物理地址: 数值}
        raise NotImplementedError

    def read(self, addresses: list) -> dict:       # {物理地址: 数值}
        raise NotImplementedError


def load_maps():
    dd = json.loads((OUT / "drawing_data.json").read_text(encoding="utf-8"))
    return dd, {a["io_id"]: a.get("address") for a in dd.get("addresses", [])}


def parse_pairs(text):
    out = {}
    for part in str(text).split(";"):
        if not part.strip():
            continue
        m = PAIR_RE.match(part)
        if not m:
            raise ValueError(f"激励/期望不可解析：{part}")
        out[m.group(1)] = m.group(2) + m.group(3)
    return out


def judge(expected, actual):
    diffs = []
    for io_id, raw in parse_pairs(expected).items():
        rhs = raw[1:] if raw.startswith("=") else raw
        got = actual.get(io_id)
        if got is None:
            diffs.append(f"{io_id} 期望{rhs} 实际无采集")
            continue
        val = float(got)
        if rhs.startswith(">="):
            ok = val >= float(rhs[2:])
        elif rhs.startswith("<="):
            ok = val <= float(rhs[2:])
        else:
            exp = float(rhs.split("±")[0])
            tol = float(rhs.split("±")[1]) if "±" in rhs else 0.0
            ok = abs(val - exp) <= tol
        if not ok:
            diffs.append(f"{io_id} 期望{rhs} 实际{val}")
    return diffs


def main(adapter, batch, instance, cpu):
    _, addr = load_maps()
    with (OUT / "test_steps.csv").open(encoding="utf-8-sig", newline="") as f:
        steps = list(csv.DictReader(f))
    adapter.connect(instance, cpu)
    cases, defects = [], []
    for s in steps:
        tid, expected = s["TEST-ID"], s["期望输出"]
        exp_ids = list(parse_pairs(expected))
        try:
            adapter.cold_start()
            adapter.write({addr[k]: v.lstrip("=") for k, v in parse_pairs(s["输入激励"]).items()})
            hold, t0, samples = int(s["保持时间(ms)"]), time.time(), []
            while (time.time() - t0) * 1000 < hold:
                raw = adapter.read([addr[k] for k in exp_ids])
                samples.append({k: raw.get(addr[k]) for k in exp_ids})
                time.sleep(SAMPLE_MS / 1000)
            if len(samples) < 5:
                raise TimeoutError(f"采样点不足：{len(samples)}")
            diffs = judge(expected, samples[-1])
            result = "通过" if not diffs else "失败"
            note = f"{batch}；初始化=冷启动；采样={SAMPLE_MS}ms×{len(samples)}"
            if diffs:
                note += "；差异=" + "；".join(diffs)
            actual = "；".join(f"{k}={samples[-1][k]}" for k in exp_ids)
        except Exception as e:      # 环境类异常：只标未执行，不判通过
            result, actual, note = "未执行", "—", f"【仿真未执行：{e}】"
        cases.append({"test_id": tid, "req_id": s["关联REQ-ID"], "scene": s["测试场景"],
                      "stimulus": s["输入激励"], "expected": expected,
                      "actual": actual, "result": result, "note": note})
        if result == "失败":
            defects.append([f"DEF-{len(defects) + 1:03d}", tid, s["关联REQ-ID"],
                            "实际输出与期望不符", note, "待定位", "待定", "",
                            "", "否（本技能仅建议）", ""])
    run = {"batch": batch,
           "meta": [["批次", batch], ["通道", type(adapter).__name__],
                    ["CPU/PLCSIM", f"{cpu}/{instance}"], ["不适用", "无"]],
           "cases": cases, "defects": defects}
    (STAGE / "sim_run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    print(f"{len(cases)} 例 / 失败 {sum(1 for c in cases if c['result'] == '失败')}")


if __name__ == "__main__":
    raise SystemExit("【仿真通道缺失：请先实现并注入 SimAdapter 后再执行】")
```

- 失败行的定位字段（链路节点/归属阶段/定位依据/建议/复测要求）必须按第 6 节补齐；`待定位`/`待定` 是占位，不得交付。
- `probe()` 返回能力清单（可写/可读/采样下限/下载权限）；探测失败按 §4.7 标未执行。

---

## 5. results.xlsx 规范

### 5.1 工作表

| 工作表 | 内容 |
|---|---|
| `00-说明` | 项目/版本/输入哈希/通道/统计/口径/限制/未修改声明 |
| `01-测试结果` | 主表，8 列，与 `test_steps.csv` 一一对应 |
| `02-问题定位` | 失败/阻塞项的定位清单（第 6 节）；无失败时保留表头并写"无" |

`00-说明` 至少包含下列键值行（键名固定，值由脚本计算或填写）：

```text
项目 | <项目名>
批次 | SIM-RUN-<YYYYMMDD-HHMMSS>
编译状态 | 编译通过 / 未执行（不得写推断）
CPU/PLCSIM | <CPU型号>/<实例名>
输入哈希 | requirements_spec.xlsx=…; drawing_data.json=…; test_steps.csv=…; results.xlsx=…
数据版本 | <DATA-V>/<ADDR-V>
需求统计 | 纳入 n 条（已确认 a / 模拟 b）；排除 m 条（待澄清 c / 已关闭 d）
用例统计 | 总 n；正常 n1 / 急停 n2 / 故障 n3 / 复位异常 n4
判定统计 | 通过 n / 失败 n / 未执行 n / 阻塞 n
通过率口径 | 通过数÷已执行数 = x%；通过数÷总数 = y%
仿真限制 | 采样周期/无法验证项/观察项/通道限制
不适用 | <类别 + 依据>（无则写"无"）
未修改上游 | 是（对照基线哈希；列出被对比文件）
```

### 5.2 主表字段（8 列，逐字、固定、不得增删改序）

```text
TEST-ID | 关联REQ-ID | 测试场景 | 输入激励 | 期望输出 | 实际输出 | 判定结果 | 备注
```

- `TEST-ID`/`关联REQ-ID`/`测试场景`/`输入激励`/`期望输出` 五列必须与 `test_steps.csv` 对应行**按列名逐字一致**（CSV 与结果表列序不同，不按位置比；含分号空格写法），便于交叉核对。
- `实际输出`：按 `IO-ID=值` 记录实测值；失败时只写差异点也允许，但必须在备注列出完整期望清单。未执行写 `—`。
- `判定结果`：只允许 `通过`/`失败`/`未执行`/`阻塞`。
- `备注`：单行文本，包含批次、初始化方式、采样点数、差异、证据文件名；不得写"基本通过/应该没问题"。

备注格式建议：

```text
SIM-RUN-20261114-101500；初始化=冷启动；采样=50ms×20；差异=IO-010 期望1 实际0；证据=sim_evidence/TEST-001-01.csv
```

### 5.3 判定词表

| 词 | 含义 | 计入 |
|---|---|---|
| `通过` | 采集值与期望完全匹配 | 通过数 |
| `失败` | 采集值与期望不符，或出现非预期安全输出 | 失败数 |
| `未执行` | 通道/授权/环境原因未运行 | 单独统计，不计通过 |
| `阻塞` | 需求不可测/点位缺失/前置缺失，无法构成有效用例 | 单独统计 |

### 5.4 生成脚本

```python
# ./output/_stage5/write_results.py
import json
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

OUT = Path("./output"); STAGE = OUT / "_stage5"
MAIN = ["TEST-ID", "关联REQ-ID", "测试场景", "输入激励",
        "期望输出", "实际输出", "判定结果", "备注"]
WIDTH = [14, 14, 22, 34, 26, 26, 10, 52]


def build(meta, cases, defects):
    wb = Workbook()
    ws0 = wb.active; ws0.title = "00-说明"
    for row in meta:
        ws0.append(row)
    ws0.column_dimensions["A"].width = 28
    ws0.column_dimensions["B"].width = 60

    ws = wb.create_sheet("01-测试结果")
    ws.append(MAIN)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.alignment = Alignment(horizontal="center", vertical="center")
    for case in cases:
        ws.append([case["test_id"], case["req_id"], case["scene"],
                   case["stimulus"], case["expected"], case["actual"],
                   case["result"], case["note"]])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for i, w in enumerate(WIDTH, start=1):
        ws.column_dimensions[chr(64 + i)].width = w
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    wd = wb.create_sheet("02-问题定位")
    wd.append(["DEFECT-ID", "TEST-ID", "REQ-ID", "失败现象", "期望vs实际",
               "链路节点(IO/BOM/TERM/CODE)", "归属阶段", "定位依据",
               "修改建议", "是否修改上游", "复测要求"])
    for d in defects:
        wd.append(d)
    wd.freeze_panes = "A2"
    wd.auto_filter.ref = wd.dimensions

    tmp = OUT / "results.tmp.xlsx"
    wb.save(tmp)
    tmp.replace(OUT / "results.xlsx")
    print(f"results.xlsx: {len(cases)} 行 / 缺陷 {len(defects)} 条")


if __name__ == "__main__":
    run = json.loads((STAGE / "sim_run.json").read_text(encoding="utf-8"))
    build(run["meta"], run["cases"], run.get("defects", []))
```

### 5.5 结果校验

- [ ] 三张表存在，主表表头逐字 8 列。
- [ ] 主表行数 = `test_steps.csv` 行数；TEST-ID 集合完全一致；五列按列名逐字一致（不按位置）。
- [ ] 判定结果仅四词；`未执行/阻塞` 均有原因；失败项有差异记录。
- [ ] 通过率口径写明（分母 = 已执行数或总数，二者分开给）。
- [ ] 无"部分通过""基本通过"等模糊判定。

---

## 6. 失败分支处理（步骤5-3）

### 6.1 全通过分支

- 条件：所有用例 `通过`（或含已说明的 `观察项`），且无未覆盖 REQ、无阻塞项。
- 动作：标记 `仿真验证通过（以采集结果为准）`，进入第 7 节构建追溯矩阵。
- 表述限制：只能写"仿真通过"，不得写"可现场运行/已验收/安全合规"。

### 6.2 失败分类（先定归属，再给建议）

| 类别 | 判定依据 | 归属阶段 |
|---|---|---|
| `CODE` 代码逻辑 | 需求/IO/端子链一致，期望值由需求可直接得出，实际输出不符；差异可定位到具体块/分支 | 阶段4（改代码→重新编译→重跑仿真） |
| `REQ` 需求矛盾/不可测 | 两条需求期望互斥；或验收准则缺参数导致无法形成确定期望；或期望与需求原文冲突 | 阶段1（修订需求，并同步全链路数据） |
| `DESIGN-IO` 点位缺失/错配 | 需求要求的信号在 `drawing_data` 中无 IO、类型不符、地址重叠/越界 | 阶段2/3（补 IO→地址→端子） |
| `DESIGN-TERM` 端子断链 | IO 有定义但端子表中无对应回路/端子，或一线多端子 | 阶段3（补端子/改回路） |
| `DESIGN-BOM` 物料不匹配 | BOM 中无对应器件，或器件类型/规格与需求不符 | 阶段2/3（补 BOM→回路→端子→JSON） |
| `TEST` 用例自身错误 | 激励/期望与验收准则不符、时序设置不合理导致误判 | 本阶段（改设计稿→重生成 CSV） |
| `ENV` 环境/采样 | 通道超时、采样不足、初始化失败、程序版本不一致 | 本阶段（重测；仍不满足标未执行） |

判定纪律：

- 先核对"期望值是否真由需求推出"；期望本身错，不得判 `CODE`。
- 先核对"点位与端子是否真的存在且一致"；链缺失时优先 `DESIGN-*`，不得把设计缺口说成代码错误。
- 分类必须有证据（需求原文引用、JSON 节点、块名/分支），不得凭印象。
- 一条失败只给一个主归属；附带影响可写在"修改建议"。

### 6.3 链路还原方法

对失败 TEST-ID：

```text
TEST-ID → 关联REQ-ID
        → drawing_data.traceability.req_to_io（或 io[].req_id）
        → io[].bom_id / bom[].io_ids
        → terminals[].io_id / loop_id / 信号名称
        → CODE-ID（块-REQ 映射：code_req_map.csv > scl 头注释 REQ > 编译日志块清单）
```

- 每个节点必须给出**原始值**，不得改写；节点缺失写 `—` 并标注"缺口"。
- CODE-ID 无法解析时，用 `CODE-<块名>` 别名并标 `【别名】`；同时在 `open_items` 记录"阶段4未提供 CODE-ID 映射"。
- 链路还原结果直接进入 `02-问题定位` 与矩阵的对应行，保证两边一致。

### 6.4 问题定位清单字段（`02-问题定位`）

```text
DEFECT-ID | TEST-ID | REQ-ID | 失败现象 | 期望vs实际 | 链路节点(IO/BOM/TERM/CODE) |
归属阶段 | 定位依据 | 修改建议 | 是否修改上游 | 复测要求
```

- `是否修改上游` 永远写 `否（本技能仅建议）`。
- `修改建议` 必须可执行、指向具体文件/块/行/字段；不写"优化一下逻辑"。
- `复测要求` 写明复测范围：单用例、关联 REQ 全部用例、或全量回归。

### 6.5 返回指引

| 归属 | 返回对象 | 必须同步更新的下游数据 | 复测范围 |
|---|---|---|---|
| `CODE` | 阶段4 `plc-scl-gen-04` | 重新编译→重新下载→`compilation_fix_shturl` 升轮次 | 失败用例 + 同 REQ 全部用例 + 受影响块的用例 |
| `REQ` | 阶段1 `req-spec-01` | 需求变更 → IO/BOM/端子/代码/测试/矩阵全部同步升版 | 受影响 REQ 全部用例 + 全链路回归 |
| `DESIGN-IO` | 阶段2/3 | IO→地址→回路→电缆→端子→`drawing_data.json` | 受影响 IO 的用例 + 矩阵重建 |
| `DESIGN-TERM` | 阶段3 | 回路/电缆/端子/JSON | 受影响回路用例 |
| `DESIGN-BOM` | 阶段2/3 | BOM→回路→端子→JSON | 受影响回路用例 |
| `TEST` | 本阶段 | 仅 `test_steps.csv`/设计稿 | 该用例 |
| `ENV` | 本阶段 | 无（记录批次差异） | 该用例 |

- 返回上游时只给"定位结果 + 建议 + 复测要求"，不代改、不代签。
- 需求变更必须提示：上游任一 ID 变化会导致六节点链路与矩阵失配，须整链重建并升 `DATA-V`/`TRACE-V`。

### 6.6 失败分支禁令

- 禁止为了让结果变绿而改期望、改激励、删用例、换判定口径；确属用例错误须在 `02-问题定位` 记 `TEST` 并留痕。
- 禁止把失败标成"待观察"后不记录。
- 禁止直接编辑 SCL、DB、IO 表、BOM、端子表、`drawing_data.json`。
- 禁止只报"失败"不给链路与归属。

---

## 7. 全链路追溯矩阵（步骤5-4）

### 7.1 行粒度

- 一行 = 一个唯一的六元组 `(REQ-ID, IO-ID, BOM-ID, TERM-ID, CODE-ID, TEST-ID)`。
- 一条 REQ 有 N 个 IO、M 条用例 → 生成 N×M 行（每个 IO 各自的 BOM/TERM 独立成行），禁止用 `;` 把多个 ID 塞进一个单元格。
- REQ 确无物理点位（纯软件/记录类）时：IO/BOM/TERM 写 `N/A`，必须在 `备注` 写依据，并列入 `open_items`；不得留空。
- 未覆盖 REQ 也要出行：`TEST-ID=—`、`链路完整性=部分`，确保缺口可见。

### 7.2 字段（固定 9 列）

```text
TRACE-ID | REQ-ID | IO-ID | BOM-ID | TERM-ID | CODE-ID | TEST-ID | 链路完整性 | 备注
```

| 字段 | 规则 |
|---|---|
| `TRACE-ID` | `TRC-<REQ数字段>-<两位序号>`，行唯一，脚本生成 |
| `REQ-ID` | 纳入测试的需求；未被覆盖的 REQ 也保留行 |
| `IO-ID` | 一个点位；确无点位写 `N/A` |
| `BOM-ID` | 该点位的物料；多物料时按"主器件"一行一值，其余在备注列 `附加BOM` |
| `TERM-ID` | 该点位对应端子；多端子时取首个并在备注列全部，禁止省略而不说明 |
| `CODE-ID` | 实现该需求的块；缺失用 `CODE-<块名>【别名】` |
| `TEST-ID` | 验证该 REQ 的用例；无用例写 `—` |
| `链路完整性` | `完整`/`部分`，判定规则见 §7.4 |
| `备注` | 关联方式（显式/回路推断）、附加节点、缺口原因、模拟标记 |

### 7.3 节点解析规则（按优先级，不得跳级猜测）

| 链路 | 解析顺序 |
|---|---|
| REQ→IO | ① `traceability.req_to_io` ② `io[].req_id` 含该 REQ；多个取全部 |
| IO→BOM | ① `io[].bom_id` ② `bom[].io_ids` 含该 IO ③ 同 `loop_id` 且该回路唯一 BOM（备注标"回路推断"） |
| IO→TERM | ① 全表 `terminals[].io_id` 精确命中 ② `terminals[].loop_id == io.loop_id` 且该回路无歧义（唯一） ③ 端子 `信号名称` 与 `io.signal` 精确且唯一；否则 N/A |
| REQ→CODE | ① `code_req_map.csv` ② `src/*.scl` 头注释 `REQ:` ③ `compilation_fix_shturl` 块清单（仅到块级）；否则 `CODE-<块名>【别名】` |
| REQ→TEST | `test_steps.csv` 中 `关联REQ-ID` 相同者；无则 `—` |

- 一律使用原始 ID，不做大小写/前后缀"纠正"；发现 ID 形态异常记入 `open_items`。
- 不允许按"看起来像"匹配；模糊匹配（信号名）仅在 §7.3 第②③步且唯一命中时可用。
- 同一 IO 对应多 BOM/多端子时：主行取首个，其余在同备注列明；若数量差异影响判定，另起一行（行仍唯一）。

### 7.4 覆盖率（100% 门禁）

```text
需求测试覆盖率 = 有≥1条用例的 REQ 数 / REQ_SET 数
链路完整率     = 链路完整性=完整的行数 / 总行数
结果覆盖率     = 有判定结果(通过/失败/未执行/阻塞)的用例数 / 用例总数
综合追溯覆盖率 = 三者最小值
```

- 判定 `完整` 的条件：六个字段均非空；`N/A` 必须有备注依据；`CODE-ID` 别名允许，但必须在 `open_items` 登记。
- 三者任一 < 100% → 矩阵状态 `未通过（覆盖率不足）`，在 `00-说明` 列缺口清单；不得写"基本覆盖"。
- 覆盖率由脚本计算并写入 `00-说明`，禁止手填。

### 7.5 反向索引（`02-反向索引`）

```text
ID | ID类型 | 关联TRACE-ID列表 | 关联说明
```

- 每个出现的 REQ/IO/BOM/TERM/CODE/TEST 都要有一条索引记录，`关联TRACE-ID列表` 用 `,` 分隔并按升序。
- 作用：改任意一处数据时，可立刻查到受影响的全部行；Excel 侧同时开启筛选与冻结首行，支持按任意 ID 检索。

### 7.6 版本与哈希

- 矩阵版本 `TRACE-V1.0`；输入或映射变化升版并记录原因。
- `00-说明` 记录：`requirements_spec.xlsx`、`drawing_data.json`、`test_steps.csv`、`results.xlsx` 的 SHA256，`drawing_data.data_version/address_version`，生成时间，批次号。
- 矩阵与 `results.xlsx` 的 TEST-ID 集合必须一致；不一致即失败，重生成。

### 7.7 生成脚本（骨架）

```python
# ./output/_stage5/build_trace.py
import csv, json, hashlib
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font

OUT = Path("./output")
HDR = ["TRACE-ID", "REQ-ID", "IO-ID", "BOM-ID", "TERM-ID", "CODE-ID", "TEST-ID", "链路完整性", "备注"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_tests():
    rows = []
    with (OUT / "test_steps.csv").open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    by_req = defaultdict(list)
    for r in rows:
        by_req[r["关联REQ-ID"]].append(r["TEST-ID"])
    return rows, by_req


def load_req_set():
    """纳入测试的需求集合；未被覆盖的 REQ 也要在矩阵中出行。"""
    wb = load_workbook(OUT / "requirements_spec.xlsx", data_only=True)
    for ws in wb.worksheets:
        hdr = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
        if hdr[:1] == ["REQ-ID"]:
            out = set()
            for r in ws.iter_rows(min_row=2, values_only=True):
                if r and r[0] and len(r) > 5 and str(r[5] or "").strip() in ("已确认", "【模拟回答】"):
                    out.add(str(r[0]).strip())
            return out
    raise SystemExit("【缺少输入：requirements_spec.xlsx 未找到六字段需求表】")


def main():
    dd = json.loads((OUT / "drawing_data.json").read_text(encoding="utf-8"))
    io = {i["io_id"]: i for i in dd.get("io", [])}
    bom = {b.get("bom_id"): b for b in dd.get("bom", [])}
    terms = dd.get("terminals", [])
    tests, test_by_req = load_tests()

    req_to_io = defaultdict(list)
    for rid, ids in (dd.get("traceability", {}).get("req_to_io") or {}).items():
        req_to_io[rid].extend(ids)
    for iid, item in io.items():
        for rid in str(item.get("req_id", "")).replace("；", ";").split(";"):
            if rid.strip():
                req_to_io[rid.strip()].append(iid)

    rows, gaps = [], []
    req_set = load_req_set() | {r["关联REQ-ID"] for r in tests}
    for rid in sorted(req_set):
        ios = sorted(set(req_to_io.get(rid, [])))
        if not ios:
            ios = [None]
        for iid in ios:
            bom_id = term_id = None
            if iid:
                bom_id = io[iid].get("bom_id") or next(
                    (x for x in bom.values() if iid in (x.get("io_ids") or [])), None)
                bom_id = bom_id.get("bom_id") if isinstance(bom_id, dict) else bom_id
                # 端子解析：先全表精确匹配 io_id，再按回路唯一命中；不得"先到先得"
                term_id = next((x.get("term_id") for x in terms if x.get("io_id") == iid), None)
                if not term_id:
                    loop = io[iid].get("loop_id")
                    hits = [x.get("term_id") for x in terms
                            if loop and x.get("loop_id") == loop and not x.get("io_id")]
                    if len(hits) == 1:
                        term_id = hits[0]
            for tid in sorted(test_by_req[rid]) or ["—"]:
                rows.append([None, rid, iid or "N/A", bom_id or "N/A", term_id or "N/A",
                             None, tid, None, ""])

    code_map = {}
    f = OUT / "code_req_map.csv"
    if f.exists():
        with f.open(encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                code_map[r["REQ-ID"]] = r["CODE-ID"]

    seq = defaultdict(int)
    for r in rows:
        seq[r[1]] += 1
        r[0] = f"TRC-{r[1].split('-')[1]}-{seq[r[1]]:02d}"
        r[5] = code_map.get(r[1], "待映射")
        na_ok = all(v != "N/A" or "依据" in (r[8] or "") for v in r[2:5])
        filled = all(v not in (None, "", "—", "待映射") for v in r[1:7])
        r[7] = "完整" if filled and na_ok else "部分"
        if r[7] == "部分":
            gaps.append(r[0])

    wb = Workbook(); ws = wb.active; ws.title = "01-追溯矩阵"
    ws.append(HDR)
    for r in rows:
        ws.append(r)
    for c in ws[1]:
        c.font = Font(bold=True); c.alignment = Alignment(horizontal="center")
    ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
    for col, w in zip("ABCDEFGHI", [20, 12, 12, 12, 12, 26, 14, 12, 40]):
        ws.column_dimensions[col].width = w

    idx = defaultdict(set)
    for r in rows:
        for v in r[1:7]:
            if v and v != "—":
                idx[v].add(r[0])
    wi = wb.create_sheet("02-反向索引")
    wi.append(["ID", "ID类型", "关联TRACE-ID列表", "关联说明"])

    def kind(s):
        if s.startswith("REQ"):
            return "REQ"
        if s.startswith("IO"):
            return "IO"
        if s.startswith("BOM"):
            return "BOM"
        if s.startswith("TERM"):
            return "TERM"
        if s.startswith("CODE"):
            return "CODE"
        if s.startswith("TEST"):
            return "TEST"
        return "N/A"

    for k in sorted(idx):
        wi.append([k, kind(k), ",".join(sorted(idx[k])), ""])

    # 00-说明：统计与口径由脚本计算，禁止手填
    ws_r = load_workbook(OUT / "results.xlsx", data_only=True)["01-测试结果"]
    judged = [r[6].value for r in ws_r.iter_rows(min_row=2) if r[0].value]
    total, complete_n = len(rows), sum(1 for r in rows if r[7] == "完整")
    req_ids = sorted({r[1] for r in rows})
    cov_req = len({r[1] for r in rows if r[6] != "—"}) / len(req_ids) if req_ids else 0
    batch = "—"
    sp = OUT / "_stage5" / "sim_run.json"
    if sp.exists():
        batch = json.loads(sp.read_text(encoding="utf-8")).get("batch", "—")
    verdict = ("仿真验证通过" if judged and all(x == "通过" for x in judged)
               else "仿真未通过" if "失败" in judged else "仿真未完全执行")
    note = wb.create_sheet("00-说明", 0)
    for k, v in [
        ("生成时间", datetime.now().strftime("%Y-%m-%dT%H:%M:%S")),
        ("矩阵版本", "TRACE-V1.0"),
        ("批次", batch),
        ("仿真结论", verdict),
        ("需求数", len(req_ids)),
        ("矩阵行数", total),
        ("需求测试覆盖率", f"{cov_req:.1%}"),
        ("链路完整率", f"{complete_n / total:.1%}" if total else "0.0%"),
        ("结果覆盖率", f"{len(judged) / len(tests):.1%}" if tests else "0.0%"),
        ("判定分布", f"通过 {judged.count('通过')} / 失败 {judged.count('失败')} / "
                     f"未执行 {judged.count('未执行')} / 阻塞 {judged.count('阻塞')}"),
        ("输入哈希", f"requirements_spec.xlsx={sha(OUT / 'requirements_spec.xlsx')[:16]}…; "
                     f"drawing_data.json={sha(OUT / 'drawing_data.json')[:16]}…; "
                     f"test_steps.csv={sha(OUT / 'test_steps.csv')[:16]}…; "
                     f"results.xlsx={sha(OUT / 'results.xlsx')[:16]}…"),
        ("数据版本", f"{dd.get('data_version', '—')} / {dd.get('address_version', '—')}"),
        ("缺口行", ", ".join(gaps) if gaps else "无"),
        ("说明", "本表由 build_trace.py 生成；N/A 节点须在备注写依据；别名 CODE-ID 记缺口；"
                 "仅仿真结论，未做现场验证"),
    ]:
        note.append([k, v])
    note.column_dimensions["A"].width = 18
    note.column_dimensions["B"].width = 80

    wb.save(OUT / "traceability_matrix.tmp.xlsx")
    (OUT / "traceability_matrix.tmp.xlsx").replace(OUT / "traceability_matrix.xlsx")
    print(f"traceability_matrix.xlsx: {len(rows)} 行 / 缺口 {len(gaps)} 行")


if __name__ == "__main__":
    main()
```

> 脚本为骨架：字段名若与本项目 `drawing_data.json` 略有差异，按实际字段增补读取分支，但**不得改变输出列名与列序**；`CODE-ID` 的"待映射"必须替换为真实映射或别名，并在缺口清单里说明。

### 7.8 完整性与一致性判定

- 每个 `REQ_SET` 需求在矩阵中有行；每个 TEST-ID 在矩阵中出现且与结果表一致。
- 每个非 `N/A` 的 IO/BOM/TERM 必须能在 `drawing_data` 中回查；每个 CODE-ID 能在 `src/` 或编译日志中回查（别名注明）。
- 行内六元组不重复；`TRACE-ID` 唯一。
- 覆盖率三项均 100%，或整体判"未通过（覆盖率不足）"并列出缺口。

---

## 8. 一致性自检（脚本）

校验器已外置到 `assets/validate_stage5.py`（**唯一事实源**，禁止在本文件内再抄一份源码）。交付前：

```bash
cp <skills>/sim-trace-05/assets/validate_stage5.py ./output/_stage5/
python ./output/_stage5/validate_stage5.py --project <项目根>
```

**输出契约**：首行 `PASS`/`FAIL`，明细逐行 ` - ` 开头，退出码 `0`=PASS、`1`=FAIL、`2`=输入缺失；只有首行 `PASS` **且**退出码 `0` 才算通过（与 `auto-flow-master-00` §12.3 G5-07 一致）。

机检项：

| # | 校验 | 判据 |
|---|---|---|
| 1 | 三份交付物存在 | 缺一即 FAIL |
| 2 | CSV 表头 | 8 列逐字（含 `前置态`/`判定时刻`） |
| 3 | 前置态 | 每条非空（T-02） |
| 4 | 判定时刻 | 整数且 ≥ `保持时间(ms)`（T-02） |
| 5 | results 表头/行数/TEST-ID 集合 | 与 CSV 完全一致 |
| 6 | 判定词 | ∈ `{通过, 失败, 未执行, 阻塞}` |
| 7 | results 与 CSV 对应列 | `TEST-ID/关联REQ-ID/测试场景/输入激励/期望输出` 按列名逐字一致 |
| 8 | 矩阵表头 / TRACE-ID 唯一 | 9 列逐字、无重复 |
| 9 | 链路完整性 | ∈ `{完整, 部分}`；`部分` 行备注必须有缺口依据（**允许缺口，不允许无依据**） |
| 10 | 需求覆盖 | `REQ_SET` ⊆ 矩阵，且每条 REQ ≥1 条用例 |
| 11 | 四类工况 | 有用例，或 `00-说明` 写 `不适用：<类别>` + 依据 |
| 12 | 失败定位 | 每个 `失败` 用例在 `02-问题定位` 有对应行 |
| 13 | 执行覆盖 | 至少 1 条 `通过/失败`，或写明 `【仿真未执行：原因】` |

（校验失败必须回到对应步骤修正，不得改校验口径，也不得删校验项来"通过"。）

---

## 9. 交付前自检清单

> **附加强制项（2026-11-16）**：本清单之外还必须逐条满足附录 Z 的 T-01~T-06，任一条不满足不得声明本阶段完成。

- [ ] 三份输出存在且真实可打开：`test_steps.csv`、`results.xlsx`、`traceability_matrix.xlsx`。
- [ ] CSV 表头逐字 8 列；results 主表逐字 8 列；矩阵逐字 9 列；无多余列、无合并单元格。
- [ ] 每条 `REQ_SET` 至少 1 条用例；异常类至少 1 条异常用例；四类工况覆盖或"不适用+依据"。
- [ ] 所有用例的激励/期望点位都能在 `drawing_data` 回查；无自造点位、无自造逻辑。
- [ ] 仿真执行有证据（批次、通道、采样、初始化）；未执行项逐条写原因，未计入通过。
- [ ] 失败项均有差异记录、链路节点、归属阶段、修改建议、复测要求；`是否修改上游` 为"否"。
- [ ] 矩阵覆盖率三项 100%（或已判"覆盖率不足"并列出缺口）；`02-反向索引` 覆盖全部 ID。
- [ ] 六节点链路无"待映射"未处理：要么补映射，要么登记 `open_items` 并标别名/缺口。
- [ ] 未修改任何上游文件（哈希对比），未下载到真实设备。
- [ ] `00-说明` 记录版本、哈希、批次、通道、统计、口径、限制；结论不夸大。
- [ ] 结论只写"仿真通过/仿真未通过/仿真未执行"，不写"现场可用/已验收/安全合规"。

---

## 10. 对话输出契约

### 10.1 完成（全部通过）

说明：

1. 三个文件路径与版本（`TRACE-V`、批次号）；
2. 需求数、用例数、四类工况计数、通过/失败/未执行/阻塞计数；
3. 覆盖率（需求/链路/结果）与分母口径；
4. 通道、PLCSIM 实例、采样周期、编译状态；
5. 明确"仅仿真结论；未做现场验证；未修改上游文件"；
6. 待复核项（模拟条目、别名 CODE-ID、观察项、N/A 节点）。

### 10.2 存在失败

- 失败 TEST-ID 清单与差异摘要；
- 每条失败的归属阶段（CODE/REQ/DESIGN/TEST/ENV）与建议动作；
- 返回阶段与复测范围；
- 未覆盖/阻塞项；
- 不声称"已定位根因"以外的结论，不保证"改完必过"。

### 10.3 阻塞/部分输出

```text
【缺少输入：...】
【工程未编译/不可下载：...】
【仿真通道缺失：...】
【需求不可测：...】
【追溯断链：...】
【覆盖率不足：...】
```

说明已生成/未生成哪些文件与行，不补假数据。

### 10.4 禁止

- 不修改上游交付物；
- 不编造仿真过程/采集值/通过率；
- 不把未执行、阻塞、部分通过说成"通过"；
- 不新增控制逻辑、不放宽判定口径、不删失败用例；
- 不输出 HMI/图纸/代码修改。

---

## 附录 A：test_steps.csv 示例（示例数据）

```csv
TEST-ID,关联REQ-ID,测试场景,输入激励,保持时间(ms),期望输出
TEST-001-01,REQ-001,正常工况:启动运行,IO-001=1; IO-002=0,IO-030=1; IO-031=1,1500,1600,IO-010=1
TEST-001-02,REQ-001,急停工况:运行中急停,IO-001=1; IO-002=0; IO-003=0,800,IO-010=0; IO-011=0
TEST-002-01,REQ-002,故障工况:反馈超时,IO-004=1; IO-005=0,3000,IO-012=1
TEST-003-01,REQ-003,复位异常工况:条件未满足复位无效,IO-006=1; IO-007=0,1000,IO-013=0
```

## 附录 B：results.xlsx 示例（示例数据）

| TEST-ID | 关联REQ-ID | 测试场景 | 输入激励 | 期望输出 | 实际输出 | 判定结果 | 备注 |
|---|---|---|---|---|---|---|---|
| TEST-001-01 | REQ-001 | 正常工况:启动运行 | IO-001=1; IO-002=0 | IO-010=1 | IO-010=1 | 通过 | SIM-RUN-…；冷启动；50ms×30；证据=… |
| TEST-001-02 | REQ-001 | 急停工况:运行中急停 | IO-001=1; IO-002=0; IO-003=0 | IO-010=0; IO-011=0 | IO-010=1; IO-011=0 | 失败 | 差异=IO-010 期望0 实际1；持续>800ms |
| TEST-002-01 | REQ-002 | 故障工况:反馈超时 | IO-004=1; IO-005=0 | IO-012=1 | — | 未执行 | 通道写入失败，重试2次未恢复 |

## 附录 C：追溯矩阵示例（示例数据）

| TRACE-ID | REQ-ID | IO-ID | BOM-ID | TERM-ID | CODE-ID | TEST-ID | 链路完整性 | 备注 |
|---|---|---|---|---|---|---|---|---|
| TRC-001-01 | REQ-001 | IO-001 | BOM-003 | X2-05 | CODE-FB-CONV | TEST-001-01 | 完整 | 显式关联 |
| TRC-001-02 | REQ-001 | IO-001 | BOM-003 | X2-05 | CODE-FB-CONV | TEST-001-02 | 完整 | 显式关联 |
| TRC-002-01 | REQ-002 | IO-004 | BOM-007 | X2-08 | CODE-FB-CONV | TEST-002-01 | 完整 | BOM按回路推断 |

## 附录 D：四类工况设计库

| 类别 | 用例模式 | 期望来源 | 常见错误 |
|---|---|---|---|
| 正常 | 启动条件全满足→动作；停止→按定义停；顺序步进；阈值触发 | 验收准则正向条款 | 漏列"保持型输出"；把无关输出写进期望 |
| 急停 | 运行中触发；保持期启动无效；复位方式；与故障并发；通道断线 | 急停/安全条款 | 只测"触发"不测"保持/复位"；未显式列安全输出 |
| 故障 | 传感器断线/超时/非法值；反馈丢失；过载；超时；非法命令 | 故障处理条款 | 自造故障码；期望值与需求不一致 |
| 复位异常 | 条件未满足复位无效；抖动复位；复位后不自动重启；掉电恢复 | 复位/上电条款 | 把"复位"当成"重启"；缺时序导致误判 |

## 附录 E：判定与统计口径

| 指标 | 公式 | 说明 |
|---|---|---|
| 需求测试覆盖率 | 有用例的 REQ / REQ_SET | 必须 100% |
| 链路完整率 | 完整行 / 总行 | `N/A` 需依据；别名 CODE-ID 记缺口 |
| 结果覆盖率 | 有判定结果的用例 / 用例总数 | 含未执行/阻塞 |
| 用例通过率 | 通过数 / 已执行数 | 与"通过数/总数"分开给 |
| 仿真结论 | 全通过=仿真验证通过；有失败=不通过；有未执行=未完全执行 | 不得混用 |

## 附录 F：工作目录

```text
output/
├── test_steps.csv
├── results.xlsx
├── traceability_matrix.xlsx
└── _stage5/
    ├── test_design.json
    ├── sim_run.json
    ├── run_manifest.json
    ├── build_tests.py
    ├── run_sim.py
    ├── write_results.py
    ├── build_trace.py
    ├── validate_stage5.py
    └── sim_evidence/
```

## 附录 G：与上游文件的只读边界

| 文件 | 权限 | 需要变更时 |
|---|---|---|
| `requirements_spec.xlsx` | 只读 | 返回阶段1，不在本阶段改 |
| `io_address.xlsx` / `io_list.xlsx` / `bom.xlsx` / `terminal_list.xlsx` | 只读 | 返回阶段2/3 |
| `drawing_data.json` | 只读 | 返回阶段3；本阶段不重导出、不改版本 |
| `src/*.scl`、`compilation_fix_shturl` | 只读 | 返回阶段4 |
| `test_steps.csv`、`results.xlsx`、`traceability_matrix.xlsx` | 本阶段写 | 重跑本阶段并升版本 |

## 附录 H：常见错误

| 错误 | 后果 | 正确做法 |
|---|---|---|
| 只验证编译通过，不验证逻辑 | 需求未验证 | 每条 REQ 至少 1 条仿真用例 |
| 用例只测正常工况 | 安全缺陷漏检 | 异常类需求补急停/故障/复位用例 |
| 期望输出写"应动作" | 不可采集、不可判定 | 写 `IO-ID=0/1` 或带容差的数值 |
| 未执行写成通过 | 结论失真 | 单独统计，不计通过 |
| 失败只写"不符合" | 无法定位 | 记录期望/实际/偏差/链路/归属 |
| 直接用代码推断结果 | 伪造仿真 | 以采集值为准 |
| 矩阵用 `;` 塞多个 ID | 无法反查 | 一行一个六元组 |
| 缺节点补造 ID | 追溯失真 | 标 `N/A`/`待映射` 并登记缺口 |
| 顺手改上游"修一下" | 越权、破坏基线 | 只输出建议与返回指引 |
| 用重试通过覆盖首次失败 | 掩盖不稳定 | 保留全部记录，标"不稳定" |

---

## 附录 Z：实机回归失败模式与强制检查

> 来源：2026-11-16 首次在 PLCSIM Advanced 上真实执行 81 条用例（不是设计推演；项目与设备信息已脱敏），
> 结果 56 通过 / 25 不符。以下每条都由**真实失败**反推，不是假设。
> 编号规则在各技能内唯一，交付前逐条打勾；任一条不满足不得声明阶段完成。
>
> **2026-11-16 修订**：T-01 的冒烟编排见 §4.1.2，T-02 的前置态/判定时刻已落为 `test_steps.csv` 第 5/7 列（见 §3.1），T-01~T-04 的机检由 §8 的 `assets/validate_stage5.py` 承担。**与正文冲突时以正文为准**。

### Z.1 默认必须真实执行（T-01 · 强制）

"全部用例未执行"**不再被接受为正常交付**。执行前先探测通道，按下列优先级取可用者：

1. PLCSIM Advanced API（同机最稳，进程内直连过程映像，不依赖 102 端口）
2. 离线回放（脚本按激励写变量、读输出）
3. S7/OPC UA（**注意**：Windows 上 102 端口常被 TIA 的 S7 路由服务占用，本地连 `PLCSIM_IP:102` 会被抢占并 RST，先探测再选型）

通道全不可用时，只能给出**阻塞结论 + 每个通道的具体失败证据**，并在 `results.xlsx` 中保持 `未执行`，不得以"设计完成"替代执行。

### Z.2 用例必须自带可复现前置态（T-02 · 强制）

每条用例除 `激励` 与 `期望` 外，必须给出：

- **前置态**：模式、权限、初始化点、工位/设备布局、故障锁存是否已清
- **冷启动方式**：内存复位(MRES) / 复位序列（含顺序！） / 无
- **判定时刻**：等于该用例的保持时间**之后**（不得提前判定，"期望 0"的用例会在 0 ms 假通过）

> 真实事故：缺前置态 → 15 条流程用例天然起不来；判定过早 → 期望 0 的用例全部假通过；复位顺序写反 → 锁存永远清不掉（必须先"整机复位"再"故障复位"）。

### Z.3 期望值必须回指实现（T-03 · 强制）

期望值必须能追到 DB/变量的**实际编码**，不得按需求文字臆造。
> 真实事故：HMI 故障码是位编码（实际 2048），用例期望写成序号 1；容量满阈值实现为"空位≤2 即满"，用例期望"未满" —— 两条都是期望值错，不是程序错。

### Z.4 可执行性自检（T-04 · 强制）

交付前每条用例必须通过：
- 全部点位有地址映射（无 `无映射/不可解析`）
- 期望表达式可被解析（`=`、`>=`、`<=`、整数/位编码）
- 保持时间与语义一致（超时类用例的保持时间应 ≥ 超时阈值）
- 前置态点位齐全（模式/权限/初始化已覆盖）

### Z.5 失败必须三分类（T-05 · 强制）

每条失败必须归入：**工装问题**（前置态/时序/比较器）/ **用例问题**（期望值/激励不足）/ **程序问题**（逻辑缺陷）。
不得把工装问题记成程序缺陷，也不得把程序缺陷记成"未执行"。

### Z.6 执行工装的已知陷阱（T-06 · 强制）

写执行脚本时必须处理：
- **STOP / MRES 期间写 M 区会被丢弃** → 必须在 Run 之后再写模式/权限
- 复位顺序：整机复位清安全锁存 → 再故障复位清故障锁存
- 符号访问需在 MRES 后重新 `UpdateTagList()`，否则报 `NotUpToDate`

### Z.7 静态门禁脚本（T-01~T-04 可机器判定）

本技能交付前**必须**执行阶段5 静态门禁：

```bash
python <skills>/auto-flow-master-00/assets/checkers/check_stage5.py --project <项目根> --results output/results.xlsx
```

退出码 `1` 即为门禁 FAIL。机检条目：缺前置态列(T-02)、缺判定时刻或早于保持时间(T-02)、
表达式不可解析或引用未定义点位(T-04)、保持时间异常、执行覆盖率为 0(T-01/G-02)。
**脚本不写死点位与用例内容**，只读项目自有的 `test_steps.csv` / `results.xlsx` / 点位表。
