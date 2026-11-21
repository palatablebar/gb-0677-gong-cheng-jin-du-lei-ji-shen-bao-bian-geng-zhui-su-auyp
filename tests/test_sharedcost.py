import csv,io,pytest
from decimal import Decimal
from app.modules.sharedcost.rules import evaluate,COLUMNS
from app.modules.sharedcost import service
from app import store
from app.errors import DomainError

HEADER=",".join(COLUMNS)

def rows_to_csv(rows):
    return (HEADER+"\n"+"\n".join(",".join(str(c) for c in r) for r in rows)+"\n").encode()

POOLS=[
 ("pool","P1","临设","2026-11","1000.00","yes","费用池登记单","池1"),
 ("pool","P2","检测","2026-11","500.00","yes","费用池登记单","池2"),
 ("pool","P3","协调","2026-11","300.00","no","待补来源","未核池"),
]

def test_sample_runs_and_balances():
    raw=service.load_sample()
    r=evaluate(raw)
    assert r["metrics"]["balanced"] is True
    for p in r["pools"]:
        assert Decimal(p["pool_total"])==Decimal(p["accepted_total"])+Decimal(p["deferred_balance"])
    assert Decimal(r["metrics"]["pool_total"])==Decimal(r["metrics"]["accepted_total"])+Decimal(r["metrics"]["deferred_total"])

def test_input_line_conservation():
    r=evaluate(service.load_sample());m=r["metrics"]
    assert m["input"]==m["pool_rows"]+m["accepted"]+m["quarantine"]+m["blank"]+m["repeated_headers"]

def test_accepted_rows_have_formal_measurement():
    r=evaluate(service.load_sample())
    for row in r["rows"]:
        assert row["measurement_basis"].split(":",1)[0] in {"计量单","签证单","发票","验收单","检测报告"}
        assert row["accepted_amount"]

def test_pool_capacity_hard_limit_quarantines_overflow():
    "整笔超池不得部分记账：E 超余量整笔隔离"
    csv=rows_to_csv(POOLS+[
        ("entry","A1","P1","2026-11","800.00","yes","计量单:JL-1","承接"),
        ("entry","A2","P1","2026-11","300.00","yes","签证单:QZ-2","超池隔离"),
    ])
    r=evaluate(csv)
    assert [x["ref"] for x in r["rows"]]==["A1"]
    assert any(q["reason"]=="POOL_EXCEEDED" and q["ref"]=="A2" for q in r["quarantine"])
    p1=next(p for p in r["pools"] if p["pool_ref"]=="P1")
    assert (p1["accepted_total"],p1["deferred_balance"])==("800.00","200.00")

def test_ordering_gives_unique_result():
    "同额两笔竞争余量，按周期+单号确定唯一承接结果"
    csv=rows_to_csv(POOLS[:2]+[
        ("entry","B2","P2","2026-11","300.00","yes","发票:FP-2","后号"),
        ("entry","B1","P2","2026-11","300.00","yes","发票:FP-1","先号"),
    ])
    r=evaluate(csv)
    assert [x["ref"] for x in r["rows"]]==["B1"]
    assert any(q["ref"]=="B2" and q["reason"]=="POOL_EXCEEDED" for q in r["quarantine"])

def test_missing_basis_quarantined():
    csv=rows_to_csv(POOLS[:1]+[("entry","C1","P1","2026-11","100.00","yes","","无依据")])
    r=evaluate(csv)
    assert r["rows"]==[] and r["quarantine"][0]["reason"]=="MEASURE_REQUIRED"

def test_bad_measurement_kind_quarantined():
    csv=rows_to_csv(POOLS[:1]+[("entry","C2","P1","2026-11","100.00","yes","内部说明:NB-1","类型不认可")])
    r=evaluate(csv)
    assert r["quarantine"][0]["reason"]=="BAD_MEASURE_KIND"

def test_unverified_source_blocked():
    "未核来源不能进入：未核池及其转入均被拒"
    csv=rows_to_csv(POOLS+[("entry","D1","P3","2026-11","100.00","yes","计量单:JL-3","未核池转入")])
    r=evaluate(csv)
    assert all(x["pool_ref"]!="P3" for x in r["rows"])
    assert any(q["reason"]=="POOL_NOT_VERIFIED" for q in r["quarantine"])

def test_unknown_pool_quarantined():
    csv=rows_to_csv(POOLS[:1]+[("entry","E1","PX","2026-11","100.00","yes","计量单:JL-4","无池")])
    r=evaluate(csv)
    assert r["quarantine"][0]["reason"]=="POOL_NOT_FOUND"

def test_duplicate_entry_kept_once():
    csv=rows_to_csv(POOLS[:1]+[
        ("entry","F1","P1","2026-11","100.00","yes","计量单:JL-5","首条"),
        ("entry","F1","P1","2026-11","100.00","yes","计量单:JL-5","重复"),
    ])
    r=evaluate(csv)
    assert len(r["rows"])==1 and any(q["reason"]=="DUPLICATE_ENTRY" for q in r["quarantine"])

def test_invalid_amount_period_flag():
    csv=rows_to_csv(POOLS[:1]+[
        ("entry","G1","P1","2026-11","abc","yes","发票:FP-6","坏金额"),
        ("entry","G2","P1","2026-13","10.00","yes","发票:FP-7","坏周期"),
        ("entry","G3","P1","2026-11","10.00","maybe","发票:FP-8","坏标志"),
    ])
    r=evaluate(csv)
    codes={q["reason"] for q in r["quarantine"]}
    assert {"INVALID_NUMBER","INVALID_TIME","INVALID_FLAG"} <= codes

def test_seal_is_stable_and_signable():
    csv=rows_to_csv(POOLS[:1]+[("entry","H1","P1","2026-11","100.00","yes","验收单:YS-1","x")])
    a=evaluate(csv);b=evaluate(csv)
    assert a["metrics"]["seal_sha256"]==b["metrics"]["seal_sha256"] and a["metrics"]["signable"] is True

def test_empty_states():
    for raw,code in [(b"","EMPTY_FILE"),(b"\n ","BLANK_ONLY"),((HEADER+"\n").encode(),"HEADER_ONLY")]:
        with pytest.raises(DomainError) as e: evaluate(raw)
        assert e.value.code==code

def test_bad_header_and_columns():
    with pytest.raises(DomainError) as e: evaluate((HEADER+"\nx\n").encode().replace(b"note",b"xx"))
    assert e.value.code=="BAD_HEADER"
    r=evaluate((HEADER+"\n"+"only,three\n").encode())
    assert r["quarantine"][0]["reason"]=="BAD_COLUMNS"

def test_idempotent_execute_no_double_booking():
    raw=service.load_sample()
    a=service.execute(raw);b=service.execute(raw)
    assert a["run_id"]==b["run_id"] and len(store.shared_history())==1
    assert a["metrics"]["accepted_total"]==b["metrics"]["accepted_total"]

def test_review_optimistic_lock_409(client):
    p=client.post("/api/sharedcost",json={"sample":service.SAMPLE}).get_json()
    u=f"/api/sharedcost/runs/{p['run_id']}/review"
    assert client.post(u,json={"version":p["version"],"decision":"已签认"}).status_code==200
    assert client.post(u,json={"version":p["version"],"decision":"退回承接"}).status_code==409

def test_failed_write_keeps_previous_version(monkeypatch):
    "写入失败时事务回滚，旧版保留；同源重试不重复记账"
    raw=service.load_sample()
    first=service.execute(raw)
    class Boom(Exception): pass
    class FakeConn:
        def __enter__(self): return self
        def __exit__(self,*a): return False
        def execute(self,*a,**k): raise Boom("disk full")
    monkeypatch.setattr(store,"connect",lambda: FakeConn())
    with pytest.raises(Boom): service.execute(raw)
    monkeypatch.undo()
    again=service.execute(raw)
    assert again["run_id"]==first["run_id"] and again["version"]==first["version"]
    assert len(store.shared_history())==1

def test_archive_contains_accepted_pools_and_quarantine(client):
    p=client.post("/api/sharedcost",json={"sample":service.SAMPLE}).get_json()
    r=client.get(f"/api/sharedcost/runs/{p['run_id']}/archive")
    data=list(csv.reader(io.StringIO(r.data.decode("utf-8-sig"))))
    kinds={row[3] for row in data[1:]}
    assert {"accepted","pool","quarantine"} <= kinds

def test_module_entrances(client):
    assert client.get("/api/sharedcost").status_code==200
    assert client.get("/sharedcost").status_code==200

def test_upload_endpoint(client):
    raw=service.load_sample()
    data={"file":(io.BytesIO(raw),"sharedcost.csv")}
    r=client.post("/api/sharedcost/upload",data=data,content_type="multipart/form-data")
    assert r.status_code==200 and r.get_json()["metrics"]["balanced"] is True

def test_money_cent_conservation():
    csv=rows_to_csv(POOLS[:1]+[("entry","I1","P1","2026-11","999.99","yes","计量单:JL-9","分币")])
    r=evaluate(csv)
    p1=next(p for p in r["pools"] if p["pool_ref"]=="P1")
    assert Decimal(p1["accepted_total"])+Decimal(p1["deferred_balance"])==Decimal("1000.00")
