# 接口

模块GET使用仓内样例，模块POST可传csv或rows与context，直接计算当前规则。/api/runs使用完整流水线并原子保存。每个阶段返回rows、quarantine、metrics；后续阶段还返回累计隔离。/api/upload接收multipart文件file。/api/runs/<id>/archive只导出一份带清单与证据的CSV。

## 共同费用承接（M8）

- `GET /api/sharedcost`：返回最近承接批次，无批次时对样例 `sharedcost.csv` 执行一次。
- `POST /api/sharedcost`：传 `csv` 文本或 `sample`，计算并原子保存；返回 rows（本期转入，逐项含计量依据）、pools（费用池与待摊余量）、quarantine（未核来源/无依据/超池等隔离）、metrics（含 `seal_sha256` 封存摘要、`balanced` 守恒标志）。
- `POST /api/sharedcost/upload`：multipart 文件 `file` 导入。
- `GET /api/sharedcost/runs`：历史承接批次；`GET /api/sharedcost/runs/<id>` 批次详情。
- `POST /api/sharedcost/runs/<id>/review`：需要 version 与 decision（`已签认`/`退回承接`），版本不符返回 409。
- `GET /api/sharedcost/runs/<id>/archive`：唯一证据导出（accepted/pool/quarantine 三类行）。

输入列：`record_type,ref,cost_code,period,amount,verified,measurement_ref,note`，`record_type` 为 `pool`/`entry`。同源同规则产生相同 run_id 与封存摘要，重跑不重复记账；写库事务失败时旧批次保留。
