# 工程进度累计申报与变更追溯

供总包项目计量审核员核对原始记录、处理差异并封存证据。

## 启动

```sh
docker compose up --build -d
docker compose exec -T app pytest -q
```

打开 http://localhost:18246 。首次进入自动运行仓内脏样例。工具条可重跑、切换样例或上传CSV。SQLite保存在命名卷records中，重建服务保留批次。

## 模块

- 1. 申报采信：`/claims`，`/api/claims`。
- 2. 清单映射：`/billitems`，`/api/billitems`。
- 3. 变更定版：`/changes`，`/api/changes`。
- 4. 累计还原：`/increment`，`/api/increment`。
- 5. 扣回核算：`/deductions`，`/api/deductions`。
- 6. 进度对账：`/valuation`，`/api/valuation`。
- 7. 签证归档：`/certificates`，`/api/certificates`。
- 8. 共同费用承接：`/sharedcost`，`/api/sharedcost`。

## 核心规则

累计申报必须减前期已审金额，变更按审批生效版本覆盖；负进度需关联冲回证据。

共同费用（临设、检测、协调）按费用池承接：每笔转入必须引用已核费用池并附正式计量依据（计量单/签证单/发票/验收单/检测报告）；未核来源、无依据、依据类型不认可、超池余量一律隔离，不得进入。逐池对平 `池总额 = 本期转入合计 + 待摊余量`，超池整笔隔离不做部分记账。承接结果按来源与规则版本封存为唯一摘要；写库 `INSERT OR IGNORE` 同源幂等不重复记账，事务失败保留旧版，签认走版本条件更新（陈旧返回409）。

## 演示

1. 打开首页，核对当次计算、差异和隔离原因。
2. 切换模块查看源行及裁决依据。
3. 重跑相同样例，批次号与行数保持一致。
4. 复核后导出一份证据CSV。版本已变化的复核提交返回409。

## 输入与输出

输入列见 `docs/DATA-DICTIONARY.md`。项目包含dirty.csv、clean.csv、legacy.csv，统一走实际导入路径。上传限制4MB，拒绝不带时区的时间。业务键按字符串保留，Decimal参与计算，空值不会当零。

`POST /api/runs` 接收sample或csv；`GET /api/runs`返回历史批次；`POST /api/runs/<id>/review`需要version与decision；`GET /api/runs/<id>/archive`返回唯一证据导出。

## 范围

样例均为虚构。单机复核工具不连接生产系统；不提供登录、远端数据库或自动支付。内存计算按4MB输入上限控制，SQLite事务保证结果完整写入。

## 目录

app为服务与规则，sample_data为输入，tests为测试，docs为定义与深度登记。
