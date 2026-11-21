# 深度登记 工程进度累计申报与变更追溯

规模：中型。使用者：总包项目计量审核员。核心规则：累计申报必须减前期已审金额，变更按审批生效版本覆盖；负进度需关联冲回证据。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 申报采信 | 查看并运行申报采信 | `/api/claims` | `app/modules/m1_claims/rules.py` | `tests/test_m1.py` |
| M2 清单映射 | 查看并运行清单映射 | `/api/billitems` | `app/modules/m2_billitems/rules.py` | `tests/test_m2.py` |
| M3 变更定版 | 查看并运行变更定版 | `/api/changes` | `app/modules/m3_changes/rules.py` | `tests/test_m3.py` |
| M4 累计还原 | 查看并运行累计还原 | `/api/increment` | `app/modules/m4_increment/rules.py` | `tests/test_m4.py` |
| M5 扣回核算 | 查看并运行扣回核算 | `/api/deductions` | `app/modules/m5_deductions/rules.py` | `tests/test_m5.py` |
| M6 进度对账 | 查看并运行进度对账 | `/api/valuation` | `app/modules/m6_valuation/rules.py` | `tests/test_m6.py` |
| M7 签证归档 | 查看并运行签证归档 | `/api/certificates` | `app/modules/m7_certificates/rules.py` | `tests/test_m7.py` |
| M8 共同费用承接 | 裁决共同费用唯一承接结果并签认 | `/api/sharedcost` | `app/modules/sharedcost/rules.py` | `tests/test_sharedcost.py` |

## 陷阱登记

| TRAP | 现象 | 朴素实现 | 本项目处理 | 处理位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-01 | 旧编码 | 默认解码失败 | 回退GB18030 | `app/modules/m1_claims/rules.py` | `tests/test_m1.py::test_legacy_encoding_real_sample` |
| TRAP-02 | BOM | 首列名多字符 | utf-8-sig | `app/modules/m1_claims/rules.py` | `tests/test_m1.py::test_bom_real_sample` |
| TRAP-03 | 带引号换行 | 拆成两条 | csv逻辑行 | `app/modules/m1_claims/rules.py` | `tests/test_m1.py::test_quoted_newline_is_one_record` |
| TRAP-05 | 列数不匹配 | 静默错列 | 隔离原行 | `app/modules/m1_claims/rules.py` | `tests/test_m1.py::test_bad_columns_real_sample` |
| TRAP-08 | 前导零ID | 编码变形 | 全程字符串 | `app/modules/m1_claims/rules.py` | `tests/test_m1.py::test_identifier_preserved_real_sample` |
| TRAP-14 | 重复键冲突 | 后写覆盖 | 保留首条并隔离冲突行 | `app/modules/m1_claims/rules.py` | `tests/test_m1.py::test_duplicate_conflict_real_sample` |
| TRAP-18 | 空态三态 | 一律成功 | 分别错误码 | `app/modules/m1_claims/rules.py` | `tests/test_m1.py::test_three_empty_states` |
| TRAP-26 | 旧版本提交 | 覆盖新结果 | 版本条件更新 | `app/store.py` | `tests/test_e2e.py::test_stale_review_409` |
| TRAP-06 | 全角累计量 | 转换失败 | Decimal归一 | `app/values.py` | `tests/test_m2.py::test_fullwidth_quantity` |
| TRAP-07 | 累计量空值 | 按零冲回 | 隔离缺失 | `app/values.py` | `tests/test_m2.py::test_real_null_not_zero` |
| TRAP-10 | 分币舍入 | 浮点误差 | 分项量化后净额守恒 | `app/modules/m5_deductions/rules.py` | `tests/test_m5.py::test_fraction_rounds_to_cent` |
| TRAP-23 | 变更生效边界 | 旧价覆盖 | 按周期选择已批版本 | `app/modules/m3_changes/rules.py` | `tests/test_m3.py::test_effective_boundary` |
| TRAP-30 | 共同费用整笔待摊 | 本期签证少计 | 池额对平：转入+待摊余量 | `app/modules/sharedcost/rules.py` | `tests/test_sharedcost.py::test_sample_runs_and_balances` |
| TRAP-31 | 超池承接 | 挤占后续责任量 | 超池整笔隔离不部分记账 | `app/modules/sharedcost/rules.py` | `tests/test_sharedcost.py::test_pool_capacity_hard_limit_quarantines_overflow` |
| TRAP-32 | 未核来源入账 | 无来源也进池 | 未核池及关联转入隔离 | `app/modules/sharedcost/rules.py` | `tests/test_sharedcost.py::test_unverified_source_blocked` |
| TRAP-33 | 缺正式计量依据 | 口头说明即转 | 仅认可五类正式凭证 | `app/modules/sharedcost/rules.py` | `tests/test_sharedcost.py::test_missing_basis_quarantined` |
| TRAP-34 | 承接重试重复记账 | 重跑金额翻倍 | run_id摘要幂等+INSERT OR IGNORE | `app/store.py` | `tests/test_sharedcost.py::test_idempotent_execute_no_double_booking` |
| TRAP-35 | 写库失败覆盖旧版 | 半成品替换已签版 | 先算后写、事务回滚保留旧版 | `app/store.py` | `tests/test_sharedcost.py::test_failed_write_keeps_previous_version` |

## 对账规则

输入原始逻辑行=最终采纳来源行+隔离来源行+重复行+空白行+分段表头。派生记录用_sources保存完整来源，因此分组不丢行。业务预期合计与上游申报合计之差等于逐行差异之和。结果按输入摘要、规则版本及参数产生唯一批次，事务写入；同源重跑只复用已有批次。

共同费用承接独立建表（sharedcost），按费用池裁决：转入按周期+单号确定顺序，逐笔校验已核池、正式计量依据与池余量，任一不满足即整笔隔离。每池强制 `pool_total = accepted_total + deferred_balance`，全部池汇总额外对平；承接结果对采纳行与池汇总规范化排序后计算 `seal_sha256`，同源同规则产生唯一可签认结果。写入先完整计算后 `INSERT OR IGNORE` 事务保存，失败回滚保留旧版；签认采用版本条件更新，陈旧提交 409。

## 已知不覆盖

4MB以上文件需预先按业务键分批；不模拟生产支付与外部回调。人工复核只变更批次状态，不改写原始记录。
