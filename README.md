# PLC 自动化工程设计技能集（六阶段流水线）

一套面向西门子 PLC 项目的**分阶段、带门禁、可追溯**的 AI 技能（Skill）集合。它把“客户一句话需求”到“可编译的 SCL 程序 + 仿真验证 + 评估归档”拆成六个阶段，每个阶段有明确的输入契约、输出契约、可机判的验收门禁，以及失败即停的终止行为。

设计初衷不是“让模型多写点东西”，而是**让模型不能糊弄**：不执行就说未执行、没编译就不许写编译通过、没有证据就不许判合格。

> **当前版本 v2.0.0**：输出从“平铺在 `output/`”改为“按阶段分目录”。变更说明见 [CHANGELOG](CHANGELOG.md)，完整说明见 [docs/](docs/)。

---

## 一、v2.0 的核心变更：输出按阶段收敛

v1.x 的所有交付物都堆在 `output/` 根目录，靠文件名区分阶段。项目一多、过程证据一多，根目录很快失控，也无法判断“这个文件到底该由哪个阶段负责”。

v2.0 固定为七个阶段目录，**目录名是契约，不得改名**：

```text
output/
├── 00-flow/              # 状态机、全流程日志、能力探测
├── 01-requirements/      # 需求规格 + 澄清日志
├── 02-scheme-io-bom/     # 方案 / IO / BOM / 多维自检
├── 03-electrical/        # 地址 / 回路 / 电缆 / 端子 / 强条 / 统一数据源
├── 04-scl/               # SCL 源码 + 编译修复日志 + DB/接口定义
├── 05-sim-trace/         # 用例 / 结果 / 追溯矩阵
└── 06-eval-archive/      # 评估报告 / 指标台账 / 归档清单
```

配套变化：

- `flow_status.json` 增加 `schema_version=2.0`、`layout_version=2.0`、`output_layout=staged`、`stage_dirs`；
- 新增布局错误码 `E00_LAYOUT_INVALID`、`E00_LAYOUT_CONFLICT`、`E00_LAYOUT_VERSION`、`E00_PATH_UNSAFE`，错误码总数 **69**；
- 过程证据放本阶段 `_work/`，不再散落根目录；
- 阶段 0 只创建 `00-flow/`，阶段 1～6 进入时各自创建目录；
- 旧平铺文件与新阶段文件并存时判 `E00_LAYOUT_CONFLICT`，要求先迁移，不自动删除。

**这是硬切**：v2.0 的技能不再读取平铺路径。从 v1.x 升级见 [§九](#九从-v1x-升级到-v20)。

---

## 二、六个阶段

| 阶段 | 技能 | 主要输入 | 主要输出（括号内为 v2.0 目录） |
|---|---|---|---|
| 1 | `req-spec-01` 需求澄清与规格化 | 客户原始需求 | `requirements_spec.xlsx`、`clarification_shturl.md`（`01-requirements/`） |
| 2 | `scheme-io-bom-02` 控制方案 / IO / BOM | 需求规格表、器件库 | `scheme.md`、`io_list.xlsx`、`bom.xlsx`、`multi_check_report.md`（`02-scheme-io-bom/`） |
| 3 | `elec-construction-03` 电气施工设计 | IO 清单、BOM、强条库 | `io_address.xlsx`、`loop_description.md`、`cable_schedule.xlsx`、`terminal_list.xlsx`、`clause_check.xlsx`、`drawing_data.json`（`03-electrical/`） |
| 4 | `plc-scl-gen-04` SCL 生成与编译闭环 | IO 地址、DB 定义、接口契约 | `src/*.scl`、`compilation_fix_shturl`（`04-scl/`） |
| 5 | `sim-trace-05` 仿真验证与追溯 | 需求、程序、全项目数据源 | `test_steps.csv`、`results.xlsx`、`traceability_matrix.xlsx`（`05-sim-trace/`） |
| 6 | `eval-archive-06` 评估与归档 | 阶段 1–5 全部交付物 | `project_evaluation_report.md`、`quality_metrics_summary.xlsx`、`project_archive_list.md`（`06-eval-archive/`） |

阶段 3 另出 `plc_tag_map.csv` 与 `plc_tag_table.xml`（变量表导入用，不计入 17 项交付物，但缺失会阻断阶段 4）；阶段 1–5 的约定交付物共 **17 项**，阶段 6 自身输出不计入该口径。

总调度技能 `auto-flow-master-00` 负责：阶段顺序、输入输出门禁、`flow_status.json` 状态机、`flow_shturl` 全流程日志、失败终止、断点续跑。它不介入任何业务设计。

```
需求 ──▶ 方案/IO/BOM ──▶ 电气设计 ──▶ SCL ──▶ 仿真/追溯 ──▶ 评估/归档
  ▲            ▲              ▲          ▲          ▲            ▲
  └────────────┴──────────────┴──────────┴──────────┴────────────┘
                    每个阶段都有输入门禁 + 输出门禁
```

---

## 三、为什么它不是“提示词合集”

### 1. 门禁是可机判的，不是形容词

每个阶段的门禁都写成硬断言：表头逐字、编号正则、状态词白名单、覆盖率数字、SHA-256 比对、退出码。例如：

- `test_steps.csv` 首行必须逐字等于 `TEST-ID,关联REQ-ID,测试场景,输入激励,前置态,保持时间(ms),判定时刻,期望输出`；
- `traceability_matrix.xlsx` 必须 9 列，`链路完整性 ∈ {完整, 部分}`，且“部分”行必须有缺口依据；
- 阶段 6 报告必须出现逐字样 `数据指纹：<16 位>` 与 `待统计 N 项`，否则判不一致。

### 2. 验证脚本与门禁同源

仓库自带校验器，输出的**首行固定为 `PASS`/`FAIL`**，退出码 `0/1/2`，可直接挂 CI：

| 脚本 | 检查什么 |
|---|---|
| `skills/auto-flow-master-00/assets/checkers/check_stage4.py` | SCL 单一写入者、NC 极性、状态量类型、实例静态化 |
| `skills/auto-flow-master-00/assets/checkers/check_stage5.py` | 用例可执行性、点位合法性、前置态、判定时刻、执行覆盖率 |
| `skills/sim-trace-05/assets/validate_stage5.py` | 三件套结构、判定词、链路完整性、需求覆盖 |
| `skills/eval-archive-06/assets/validate_stage6.py` | 指标台账、指纹、归档核对、上游未被改动 |

### 3. 模拟裁决必须留痕

当信息缺口必须由模型“先假定一个值”时，产物上必须就地标 `【模拟裁决】`，并写清依据、影响、风险；禁止改写成“已确认/已验证/合规”。阶段 5、6 的**数值与结论不允许模拟**——仿真没跑就是 `未执行`，评估没数据就是 `待统计`。

### 4. 补偿性设计：编译通过 ≠ 可交付

阶段 4 结束一律记 `+logic_unverified`；阶段 5 必须先跑 3 条冒烟（正常/急停/复位），跑通了才清除这个后缀。避免“编译 0 error 就当程序能用”。

---

## 四、仓库结构

```text
skills/
├── auto-flow-master-00/          总调度（状态机、门禁、日志）
│   └── assets/checkers/          阶段 4/5 静态门禁脚本 + SHA256SUMS
├── req-spec-01/                  阶段 1
├── scheme-io-bom-02/             阶段 2
├── elec-construction-03/         阶段 3
├── plc-scl-gen-04/               阶段 4
├── sim-trace-05/                 阶段 5
│   └── assets/validate_stage5.py
└── eval-archive-06/              阶段 6
    └── assets/                  采集、报告渲染、校验
tools/
├── ci_verify.py                  仓库级一致性自检
├── smoke_stage5.py               门禁夹具测试（PASS/FAIL 双向验证）
└── regen_sha.py                  改脚本后重算校验和
docs/
├── 自动化项目六阶段技能集说明文档_v2.0.md/.docx/.pdf
└── 分阶段输出目录改造方案_v2.0.md
```

> 七个技能**必须安装到同一父目录**：`00` 里引用的是 `<skills>/sim-trace-05/assets/...` 这类同级路径，拆开装会断链。

---

## 五、安装

技能宿主只认 `<技能根>/<技能名>/SKILL.md` 这个布局（例如 DSH 是 `~/.dsh/skills/`）。

**Windows（PowerShell）**

```powershell
$dest = "$env:USERPROFILE\.dsh\skills"
Copy-Item -Recurse -Force .\skills\* $dest\
Get-ChildItem $dest -Directory | Where-Object { $_.Name -match '-\d\d$' } | Select-Object Name
```

**macOS / Linux**

```bash
dest="$HOME/.dsh/skills"
mkdir -p "$dest" && cp -r skills/* "$dest"/
ls "$dest"
```

装完确认七个目录同级存在，且 `auto-flow-master-00/assets/checkers/` 与 `sim-trace-05/assets/` 都在。

---

## 六、环境要求

| 依赖 | 必需性 | 说明 |
|---|---|---|
| Python ≥ 3.9 + `openpyxl` | **必需** | 所有 xlsx 读写与校验脚本 |
| 支持 Skill 的宿主（如 DSH） | **必需** | 负责加载 `SKILL.md` |
| TIA Portal V21 + Openness + 用户组权限 | 可选 | 阶段 4 真编译、阶段 5 真下载所需；没有则走“编译未执行/仿真未执行”降级 |
| PLCSIM Advanced | 可选 | 阶段 5 真执行所需 |
| 器件库 `device_library.xlsx`、强条库 `clause_library.xlsx` | 可选 | 由使用者自备，**不随仓库分发** |

```bash
pip install openpyxl
```

没有 TIA 也能跑完 1、2、3、6 阶段与 5 的设计部分，只是编译与仿真会被如实标为“未执行”，不会伪造结果。

---

## 七、快速验证

```bash
python tools/ci_verify.py        # 125 项契约自检，应输出 PASS、退出码 0
python tools/smoke_stage5.py     # 用临时夹具跑门禁，应看到 PASS/FAIL 双向结果
```

`smoke_stage5.py` 会在 `build/smoke_project/` 现场生成最小夹具（已加入 `.gitignore`），构造合格数据与三类缺陷数据（判定时刻早于保持时间、缺口行无依据、阶段 6 缺输入），断言校验器分别返回 `PASS/0` 与 `FAIL/1|2`。它验证的是门禁本身，不代表任何真实项目已通过。

---

## 八、项目侧输出布局（v2.0）

```text
<项目根>/
├── input/                        # 客户输入、器件库、强条库（可选 stage6_stats.json）
├── output/
│   ├── 00-flow/
│   │   ├── flow_status.json
│   │   ├── flow_shturl
│   │   └── capabilities.json
│   ├── 01-requirements/
│   ├── 02-scheme-io-bom/
│   ├── 03-electrical/
│   ├── 04-scl/
│   │   ├── src/                  # 每块一个 .scl
│   │   ├── compilation_fix_shturl
│   │   ├── db_definitions.xlsx
│   │   └── interface_contract.md
│   ├── 05-sim-trace/
│   │   └── _work/
│   └── 06-eval-archive/
│       ├── _work/
│       └── inputs/stats.json     # 可选
└── archive/<project_id>/         # 按阶段目录归档，默认排除 _work/
```

规则：

1. `output/` 根目录只允许七个阶段目录（可选一个 `README.md`），不得放交付物；
2. 目录名固定、大小写固定，不允许多余空格；
3. 过程证据（脚本副本、中间 json、日志）只放本阶段 `_work/`；
4. `04-scl/src/` 只放 OB/FB/FC 的 `.scl`，唯一例外是 `src/使用说明/` 子目录；
5. 归档目录与阶段目录一一对应；`00-flow/` 默认不入归档，需要时显式包含。

---

## 九、从 v1.x 升级到 v2.0

v2.0 不自动迁移，也不删除旧文件；仓库 `0.2.0`（对应文档 v1.1）升级同样适用。推荐步骤：

1. **整包备份** `output/`；
2. 在 `output/` 下创建七个阶段目录；
3. 按下表移动交付物（只移动，不改文件名）；
4. 移动 `flow_status.json`、`flow_shturl`、`capabilities.json` 到 `00-flow/`；
5. 在 `flow_status.json` 写入 `layout_version: "2.0"`、`output_layout: "staged"` 与 `stage_dirs`；
6. 确认 `output/` 根目录不再有平铺交付物，再续跑；
7. 若新旧文件并存，门禁会判 `E00_LAYOUT_CONFLICT`——此时不要手工删旧文件，先比对再迁移。

| 旧路径（v1.x） | 新路径（v2.0） |
|---|---|
| `output/requirements_spec.xlsx` | `output/01-requirements/requirements_spec.xlsx` |
| `output/clarification_shturl.md` | `output/01-requirements/clarification_shturl.md` |
| `output/scheme.md`、`io_list.xlsx`、`bom.xlsx`、`multi_check_report.md` | `output/02-scheme-io-bom/` |
| `output/io_address.xlsx`、`loop_description.md`、`cable_schedule.xlsx`、`terminal_list.xlsx`、`clause_check.xlsx`、`drawing_data.json` | `output/03-electrical/` |
| `output/plc_tag_map.csv`、`plc_tag_table.xml` | `output/03-electrical/` |
| `output/src/*.scl` | `output/04-scl/src/` |
| `output/compilation_fix_shturl`、`db_definitions.xlsx`、`interface_contract.md` | `output/04-scl/` |
| `output/test_steps.csv`、`results.xlsx`、`traceability_matrix.xlsx` | `output/05-sim-trace/` |
| `output/project_evaluation_report.md`、`quality_metrics_summary.xlsx`、`project_archive_list.md` | `output/06-eval-archive/` |
| `output/flow_status.json`、`flow_shturl`、`capabilities.json` | `output/00-flow/` |

迁移脚本尚未随仓库提供；上表即完整映射，可据此批量移动。迁移后必须重跑对应阶段的门禁，历史结论不因搬迁自动继承。

---

## 十、约定与错误码

- 状态枚举：`pending / running / success / failed / blocked / waiting_customer / skipped / deviation`
- 完成范围：`source_only / compile_checked`，后缀 `+simulated / +logic_unverified / +untested / +eval_partial`
- 错误码前缀：`E00` 参数与布局、`E01–E06` 各阶段输入、`E07–E09` 代码与编译、`E10–E13` 流程与产物、`E14` 仿真追溯、`E15` 评估归档；共 **69** 个
- 回归编号：`R-`（需求）、`B-`（BOM/IO）、`S-`（SCL）、`T-`（测试）、`EL-`（电气）、`ENC-`（编码）、`G-`（门禁脚本）

---

## 十一、已知限制

1. **不替代人工设计审核**：产出是“可评审的初稿”，不是施工图。
2. **编译通过 ≠ 逻辑正确**：阶段 4 只保证语法与接口，逻辑正确性靠阶段 5 的实机执行证明。
3. **门禁只做形式校验**：它拦得住“格式不对、编号乱、覆盖率不够”，拦不住“用例设计得不合理”。
4. **不产出图纸**：阶段 3 只出结构化数据与计算依据，EPLAN/CAD 图面需人工完成；因此指标 `M-12`（图纸一次审核通过率）恒为 `未开展`。
5. **库数据依赖使用者提供**：器件库、强条库不随仓库分发，缺失时相应指标记 `待统计`。
6. **未提供自动迁移脚本**：v1.x → v2.0 需按 §九 映射手工移动。
7. **CI 覆盖有限**：`ci_verify.py` 校验契约文本与脚本一致性，`smoke_stage5.py` 只覆盖阶段 5/6 的部分门禁；没有阶段 1–6 全链路回归，也没有真实 TIA 导入/编译测试。

## 十二、文档

- [技能集说明文档 v2.0（Markdown）](docs/自动化项目六阶段技能集说明文档_v2.0.md)
- [技能集说明文档 v2.0（Word）](docs/自动化项目六阶段技能集说明文档_v2.0.docx)
- [技能集说明文档 v2.0（PDF）](docs/自动化项目六阶段技能集说明文档_v2.0.pdf)
- [分阶段输出目录改造方案 v2.0](docs/分阶段输出目录改造方案_v2.0.md)
- [变更记录](CHANGELOG.md)

## 十三、免责声明

本项目用于辅助工业控制工程的设计与文档编制，**不构成安全评估、合规认证或验收结论**。安全功能（急停、安全门、安全继电器、联锁）必须由具备资质的人员按适用标准独立设计与验证，不得仅依赖本工具的输出。任何下载、在线修改、强制操作都必须由现场负责人确认后方可执行。

## 十四、许可

MIT，详见 [LICENSE](LICENSE)。