import hashlib,csv,io,json,time
from datetime import datetime,timezone
from app.config import ROOT,RULE_VERSION
from app.errors import DomainError
from app.modules.sharedcost.rules import evaluate,COLUMNS
from app import store

SAMPLE="sharedcost.csv"

def load_sample(name=SAMPLE):
    if name not in {SAMPLE}: raise DomainError("BAD_SAMPLE","样例不存在",404)
    return (ROOT/"sample_data"/name).read_bytes()

def digest(raw,params=None):
    return hashlib.sha256(raw+json.dumps(params or {},sort_keys=True,ensure_ascii=False).encode()+RULE_VERSION.encode()).hexdigest()

def manifest(raw,started):
    return {"input_sha256":hashlib.sha256(raw).hexdigest(),"rule_version":RULE_VERSION,
            "generated_at":datetime.now(timezone.utc).isoformat(),"elapsed_ms":round((time.monotonic()-started)*100,2)}

def calculate(raw,params=None):
    started=time.monotonic()
    result=evaluate(raw)
    run_id=digest(raw,params)[:20]
    return {**result,"run_id":run_id,"manifest":manifest(raw,started),"parameters":params or {}}

def execute(raw,params=None):
    # 先完整计算再写库：计算阶段任何异常都不会触碰旧批次
    result=calculate(raw,params)
    return store.save_shared(result["run_id"],result)

def build_archive(run):
    stream=io.StringIO(newline="");writer=csv.writer(stream)
    meta=run["manifest"]
    writer.writerow(["run_id","input_sha256","rule_version","kind","ref","pool_ref","amount_or_balance","measurement_ref","reason","evidence"])
    for row in run["rows"]:
        writer.writerow([run["run_id"],meta["input_sha256"],meta["rule_version"],"accepted",row.get("ref"),
                         row.get("pool_ref"),row.get("accepted_amount"),row.get("measurement_basis"),
                         row.get("status",""),json.dumps({k:v for k,v in row.items() if not k.startswith("_")},ensure_ascii=False)])
    for s in run["pools"]:
        writer.writerow([run["run_id"],meta["input_sha256"],meta["rule_version"],"pool",s["pool_ref"],
                         s["pool_ref"],s["deferred_balance"],"",f"待摊余量（池额{s['pool_total']}/转入{s['accepted_total']}）",
                         json.dumps(s,ensure_ascii=False)])
    for row in run["quarantine"]:
        writer.writerow([run["run_id"],meta["input_sha256"],meta["rule_version"],"quarantine",row.get("ref",""),
                         row.get("cost_code",""),row.get("amount",""),row.get("measurement_ref",""),
                         row.get("reason",""),json.dumps({k:v for k,v in row.items() if not k.startswith("_")},ensure_ascii=False)])
    return "﻿"+stream.getvalue()
