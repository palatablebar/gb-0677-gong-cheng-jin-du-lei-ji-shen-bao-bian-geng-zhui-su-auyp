import csv,io,hashlib,json
from datetime import datetime
from app.values import number,money
from app.reasons import reject
from app.errors import DomainError
from app.config import RULE_VERSION

COLUMNS=["record_type","ref","cost_code","period","amount","verified","measurement_ref","note"]
POOL_TYPES={"pool","费用池"};ENTRY_TYPES={"entry","转入"}
TRUE={"yes","true","1","y","是","已核"};FALSE={"no","false","0","n","否","未核"}
# 需要正式计量依据的转入凭证类型
MEASURE_KINDS={"计量单","签证单","发票","验收单","检测报告"}
REASONS={
 "BAD_COLUMNS":"列数不匹配",
 "EMPTY_VALUE":"必填值为空",
 "INVALID_NUMBER":"金额格式错误",
 "INVALID_TIME":"周期格式错误",
 "BAD_RECORD_TYPE":"记录类型无法识别",
 "INVALID_FLAG":"已核标志无法识别",
 "POOL_DUPLICATE":"费用池编号重复登记",
 "POOL_NOT_VERIFIED":"费用池来源未核",
 "POOL_NOT_FOUND":"引用的费用池不存在",
 "MEASURE_REQUIRED":"缺少正式计量依据",
 "BAD_MEASURE_KIND":"计量依据类型不被认可",
 "DUPLICATE_ENTRY":"转入单号重复",
 "POOL_EXCEEDED":"承接金额超过费用池余量",
}

def decode(raw):
    for encoding in ("utf-8-sig","gb18030"):
        try: return raw.decode(encoding),encoding
        except UnicodeDecodeError: continue
    raise DomainError("ENCODING","无法识别文件编码")

def _period_ok(value):
    try: return len(value)==7 and datetime.strptime(value,"%Y-%m") is not None
    except ValueError: return False

def _flag(value):
    text=str(value).strip().lower()
    if text in TRUE: return True
    if text in FALSE: return False
    raise DomainError("INVALID_FLAG",REASONS["INVALID_FLAG"])

def parse(raw):
    text,encoding=decode(raw)
    if not text: raise DomainError("EMPTY_FILE","文件为空")
    if not text.strip(): raise DomainError("BLANK_ONLY","全部为空行")
    stream=csv.reader(io.StringIO(text,newline=""))
    header=next(stream,None)
    if header!=COLUMNS: raise DomainError("BAD_HEADER","表头不匹配")
    pools=[];entries=[];bad=[];seen_pool={};seen_entry=set()
    blank=repeated=count=0
    try:
        for cells in stream:
            count+=1;line=stream.line_num
            if not cells or not any(c.strip() for c in cells): blank+=1;continue
            if cells==header: repeated+=1;continue
            row={"_line":line,"_sources":[line],"_raw":cells}
            if len(cells)!=len(COLUMNS):
                bad.append(reject(row,"BAD_COLUMNS",REASONS["BAD_COLUMNS"]));continue
            row.update(dict(zip(COLUMNS,[x.strip() for x in cells])))
            rtype=row["record_type"].lower()
            if rtype in POOL_TYPES: _parse_pool(row,cells,pools,bad,seen_pool)
            elif rtype in ENTRY_TYPES: _parse_entry(row,entries,bad,seen_entry)
            else: bad.append(reject(row,"BAD_RECORD_TYPE",REASONS["BAD_RECORD_TYPE"]))
    except csv.Error: raise DomainError("BAD_CSV","引号未闭合或文件损坏")
    if count==0: raise DomainError("HEADER_ONLY","仅有表头")
    if not pools and not entries and not bad: raise DomainError("BLANK_ONLY","全部为空行")
    return pools,entries,bad,{"input":count,"pool_rows":len(pools),"entry_rows":len(entries),
                             "quarantine":len(bad),"blank":blank,"repeated_headers":repeated,"encoding":encoding}

def _parse_pool(row,cells,pools,bad,seen):
    ref=row["ref"]
    if not ref or not row["cost_code"] or not row["period"]:
        bad.append(reject(row,"EMPTY_VALUE",REASONS["EMPTY_VALUE"]));return
    if ref in seen:
        bad.append(reject(row,"POOL_DUPLICATE",REASONS["POOL_DUPLICATE"]));return
    try:
        if not _period_ok(row["period"]): raise DomainError("INVALID_TIME",REASONS["INVALID_TIME"])
        total=number(row["amount"])
        if total<0: raise DomainError("INVALID_NUMBER","费用池金额不能为负")
        verified=_flag(row["verified"])
    except DomainError as e:
        bad.append(reject(row,e.code,e.message));return
    seen[ref]=True
    pools.append({**row,"record_type":"pool","pool_ref":ref,"pool_total":money(total),
                  "verified":verified,"category":row["cost_code"]})

def _parse_entry(row,entries,bad,seen):
    ref=row["ref"]
    if not ref or not row["cost_code"] or not row["period"] or not row["amount"]:
        bad.append(reject(row,"EMPTY_VALUE",REASONS["EMPTY_VALUE"]));return
    if ref in seen:
        bad.append(reject(row,"DUPLICATE_ENTRY",REASONS["DUPLICATE_ENTRY"]));return
    try:
        if not _period_ok(row["period"]): raise DomainError("INVALID_TIME",REASONS["INVALID_TIME"])
        amount=number(row["amount"])
        if amount<=0: raise DomainError("INVALID_NUMBER","转入金额必须为正")
        _flag(row["verified"])
    except DomainError as e:
        bad.append(reject(row,e.code,e.message));return
    seen.add(ref)
    entries.append(row)

def evaluate(raw,context=None):
    context=context or {}
    pools,entries,intake_bad,intake=parse(raw)
    bad=list(intake_bad);good=[]
    intake_quarantine=len(intake_bad)
    pool_map={p["pool_ref"]:p for p in pools}
    # 未核费用池整体不可承接：池保留在汇总中（余额全部待摊），关联转入在此裁决隔离
    verified_pools={ref for ref,p in pool_map.items() if p["verified"]}
    remaining={ref:number(p["pool_total"]) for ref,p in pool_map.items()}
    accepted_by_pool={ref:[] for ref in pool_map}
    for row in sorted(entries,key=lambda x:(x["period"],x["ref"])):
        ref=row["cost_code"];basis=row["measurement_ref"]
        if ref not in pool_map:
            bad.append(reject(row,"POOL_NOT_FOUND",REASONS["POOL_NOT_FOUND"]));continue
        if ref not in verified_pools:
            bad.append(reject(row,"POOL_NOT_VERIFIED",REASONS["POOL_NOT_VERIFIED"]));continue
        if not basis:
            bad.append(reject(row,"MEASURE_REQUIRED",REASONS["MEASURE_REQUIRED"]));continue
        kind=basis.split(":",1)[0].strip()
        if kind not in MEASURE_KINDS:
            bad.append(reject(row,"BAD_MEASURE_KIND",REASONS["BAD_MEASURE_KIND"]));continue
        try:
            amount=money(number(row["amount"]))
        except DomainError as e:
            bad.append(reject(row,e.code,e.message));continue
        if number(amount)>remaining[ref]:
            bad.append(reject(row,"POOL_EXCEEDED",
                              f"{REASONS['POOL_EXCEEDED']}（池余量 {money(remaining[ref])}）"));continue
        remaining[ref]-=number(amount)
        record={**row,"record_type":"entry","pool_ref":ref,"category":pool_map[ref]["category"],
                "accepted_amount":amount,"measurement_basis":basis,"status":"承接"}
        good.append(record);accepted_by_pool[ref].append(record)
    summary=[]
    for ref in sorted(pool_map):
        pool=pool_map[ref];accepted=sum((number(r["accepted_amount"]) for r in accepted_by_pool[ref]),number("0"))
        total=number(pool["pool_total"]);left=total-accepted
        if left<0: raise DomainError("POOL_EXCEEDED","费用池承接超过池额")
        summary.append({"pool_ref":ref,"category":pool["category"],"period":pool["period"],
                        "verified":pool["verified"],"pool_total":money(total),
                        "accepted_total":money(accepted),"deferred_balance":money(left),
                        "entry_count":len(accepted_by_pool[ref])})
    # 守恒：池总额 = 本期转入 + 待摊余量
    for s in summary:
        if number(s["pool_total"])!=number(s["accepted_total"])+number(s["deferred_balance"]):
            raise DomainError("UNBALANCED","共同费用池未对平")
    accepted_amt=sum((number(r["accepted_amount"]) for r in good),number("0"))
    deferred_amt=sum((number(s["deferred_balance"]) for s in summary),number("0"))
    pool_amt=sum((number(s["pool_total"]) for s in summary),number("0"))
    if pool_amt!=accepted_amt+deferred_amt: raise DomainError("UNBALANCED","共同费用总额未对平")
    sealed={"accepted":sorted(({k:v for k,v in r.items() if not k.startswith("_")} for r in good),
                              key=lambda x:(x["period"],x["ref"])),
            "pools":summary}
    seal=hashlib.sha256(json.dumps(sealed,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()
    # 总笔数守恒：输入逻辑行 = 池登记 + 转入采纳 + 全部隔离 + 空行 + 分段表头
    if intake["input"]!=intake["pool_rows"]+len(good)+len(bad)+intake["blank"]+intake["repeated_headers"]:
        raise DomainError("UNBALANCED","共同费用来源行未对平")
    metrics={**intake,"pools":len(summary),"accepted":len(good),"accepted_total":money(accepted_amt),
             "deferred_total":money(deferred_amt),"pool_total":money(pool_amt),
             "intake_quarantine":intake_quarantine,"stage_quarantine":len(bad)-intake_quarantine,
             "quarantine":len(bad),"balanced":True,"seal_sha256":seal,
             "signable":len(good)>0,"rule_version":RULE_VERSION}
    return {"rows":good,"pools":summary,"quarantine":bad,"metrics":metrics}
