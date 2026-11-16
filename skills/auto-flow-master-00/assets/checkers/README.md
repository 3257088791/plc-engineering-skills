# 阶段静态门禁（项目无关）

配套 `auto-flow-master-00` 附录 Z 的 G-01 / G-02 门禁。**只读项目自有产物**，不写死任何项目名、器件名、点位名。

## 1. 为什么需要

首个真实执行项目（81 条用例上 PLCSIM）暴露了 25 条不符，根因分四类：业务拒绝被当故障、NC 未取反、状态量用 Bool、用例缺前置态与判定时刻。这些**都能静态判定**，不必等到实机。

## 2. 用法

```bash
# 阶段4：扫 src/*.scl（单一写入者 / NC 极性 / 状态量类型 / 实例静态化 / 锁存上电屏蔽）
python check_stage4.py --project <项目根> [--profile rules.json] [--json out.json] [--skip CHK-S4-01 ...]

# 阶段5：扫 test_steps.csv（前置态列 / 判定时刻 / 表达式 / 点位合法性 / 执行覆盖）
python check_stage5.py --project <项目根> [--results output/results.xlsx] [--profile rules.json]
```

退出码：`0` = PASS，`1` = FAIL（可挂 CI 或编排器门禁），`2` = 输入缺失。

依赖：`openpyxl`（仅当用 xlsx 作为点位/结果来源时需要；有 `plc_tag_map.csv` 时不需要）。

## 3. 规则表

### check_stage4.py

| 规则 | 对应条目 | 级别 | 判定内容 |
|---|---|---|---|
| CHK-S4-01 | S-03 | FAIL | 同一**全局符号**被 ≥2 个块写入（单一写入者） |
| CHK-S4-02 | S-04 | WARN | HMI/模式/权限类符号既被写入又被当条件读（输入显示混用） |
| CHK-S4-03 | S-02 | FAIL | 常闭(NC)点在 `IF/ELSIF/WHILE` 条件内未取反 |
| CHK-S4-04 | S-02 | WARN | 有锁存量但全工程无 `FirstScan/OB100` 上电屏蔽 |
| CHK-S4-05 | S-05 | FAIL | SCL 声明中状态/编码量用 `Bool` |
| CHK-S4-06 | S-05 | FAIL | 变量表中状态/编码量用 `Bool`（如 `INT_SeqStep`） |
| CHK-S4-07 | — | FAIL | `R_TRIG/TON/CTU` 等实例声明在 `VAR_TEMP` |
| CHK-S4-08 | S-01 | WARN | 业务类信号与故障/锁存量共存，需人工确认未进故障锁存 |

### check_stage5.py

| 规则 | 对应条目 | 级别 | 判定内容 |
|---|---|---|---|
| CHK-S5-01 | T-02 | FAIL | 缺「前置态」列，或前置态为空 |
| CHK-S5-02 | T-02 | FAIL | 缺「判定时刻」列，或判定时刻早于保持时间 |
| CHK-S5-03 | T-04 | FAIL | 激励/期望表达式不可解析或算子越界 |
| CHK-S5-04 | T-04 | FAIL | 引用了点位表之外的 IO-ID |
| CHK-S5-05 | T-04 | FAIL | 保持时间不可解析或低于下限 |
| CHK-S5-06 | T-03 | FAIL | 期望值为空或非整数 |
| CHK-S5-07 | T-02 | WARN | 场景含"超时"语义但保持时间明显偏短 |
| CHK-S5-08 | T-01/G-02 | FAIL | 执行覆盖率 = 0（结果全为未执行/阻塞） |
| CHK-S5-09 | E-02 | FAIL | 结果判定词不在白名单 |

## 4. 自定义 profile

所有语义关键词都可覆盖，换行业/换设备时只改 profile，不改脚本：

```json
{
  "naming": {
    "fault": ["fault", "alarm", "故障", "异常"],
    "latch": ["latch", "锁存"],
    "state": ["step", "seq", "code", "步序", "工步"],
    "hmi": ["hmi", "display", "画面"],
    "mode": ["mode", "auth", "模式", "权限"],
    "business": ["full", "满", "无车", "未付"]
  },
  "limits": {"min_hold_ms": 200},
  "skip": ["CHK-S4-08"]
}
```

## 5. 已知边界（别当它万能）

- **只做静态判定**：不执行、不编译、不下载，无法证明逻辑正确，只能拦住"已知会错"的写法
- **语义判断靠命名**：命名混乱的项目会漏报；`CHK-S4-08` 只是提醒人工复核，不是结论
- **不能替代真实执行**：T-01 要求至少 1 条真跑，本脚本只检查"有没有跑过"
- 注释里的关键词可能造成误判；发现误报请用 `--skip` 或调 profile，**不要改判定口径**