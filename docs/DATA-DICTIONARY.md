# 计量定义

claim_id唯一；item为清单编码，支持钢筋与001等别名。period为YYYY-MM。累计数量按t或m³保存，当前周期工程量=本次累计-前期已审累计。previous_revisions参数可指定更正后的前审数量，重新计算形成不同批次，不覆盖旧证据。

C0原始价100元，C1自2026-11生效为120元，DRAFT未批准不可结算。负进度必须reversal=approved作为已批冲回标记。扣留质保金5%、预付款扣回10%分别按分量化，净额=本期总额-质保金-预付款扣回，负进度同步冲回扣留。reported为原申报净额，差异=复算净额-reported。

业务ID和超大整数按文本保形；Decimal参与数量金额计算，对外序列化为字符串。哨兵集合定义在app/values.py，缺失值不能当零。所有时间带UTC偏移，先转UTC比较，业务日按指定地区划分。区间统一[start,end)。重复业务键保留第一条、完全相同行计重复；值冲突行隔离且保留原值。空文件、全空白、仅表头分开拒绝。

运行清单包括输入sha256、规则版本、参数、生成时刻与耗时。源行编号以CSV解析器的物理结束行号表示，引号内换行不增加记录数。输入超过4MB返回413，非法表头和类型返回422，失效版本复核返回409。

## 共同费用承接（sharedcost.csv）

列：`record_type,ref,cost_code,period,amount,verified,measurement_ref,note`。

- `record_type`：`pool`（费用池登记，兼容中文“费用池”）或 `entry`（转入，兼容中文“转入”），其他值隔离。
- 池行：`ref`为费用池编号（同号重复登记隔离），`cost_code`为费用类别（临设/检测/协调等），`amount`为池总额（非负），`verified`为来源已核标志（yes/true/1/是/已核 为真；no/false/0/否/未核 为假；其他隔离）。未核池整体不可承接，其关联转入以 `POOL_NOT_VERIFIED` 隔离。
- 转入行：`ref`为转入单号（重复隔离 `DUPLICATE_ENTRY`），`cost_code`引用费用池编号（不存在隔离 `POOL_NOT_FOUND`），`amount`为本次转入金额（必须为正，Decimal计算、按分量化）。
- `measurement_ref`为正式计量依据，空值隔离 `MEASURE_REQUIRED`；前缀必须是 计量单/签证单/发票/验收单/检测报告 之一，否则 `BAD_MEASURE_KIND`。
- 承接后累计不得超过池余量，超出整笔隔离 `POOL_EXCEEDED`（不做部分记账）；每池对平 `池总额=本期转入合计+待摊余量`，待摊余量为非负余额，留待后续周期。
- 裁决顺序按 `period,ref` 排序确定，保证同源唯一结果；输出含 `seal_sha256` 封存摘要。