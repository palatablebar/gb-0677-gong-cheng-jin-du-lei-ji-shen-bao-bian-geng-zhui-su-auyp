import sqlite3,json
from pathlib import Path
from app.config import DATA_DIR
from app.errors import DomainError
def connect():
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(DATA_DIR/"records.db",timeout=20)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY,payload TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,decision TEXT NOT NULL DEFAULT '待复核')")
    db.execute("CREATE TABLE IF NOT EXISTS sharedcost (id TEXT PRIMARY KEY,payload TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,decision TEXT NOT NULL DEFAULT '待承接签认')")
    return db
def save(run_id,payload):
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO runs(id,payload) VALUES (?,?)",(run_id,json.dumps(payload,ensure_ascii=False)))
    return get(run_id)
def get(run_id):
    with connect() as db: row=db.execute("SELECT payload,version,decision FROM runs WHERE id=?",(run_id,)).fetchone()
    if not row: raise DomainError("NOT_FOUND","批次不存在",404)
    return {**json.loads(row[0]),"version":row[1],"decision":row[2]}
def latest():
    with connect() as db: row=db.execute("SELECT id FROM runs ORDER BY rowid DESC LIMIT 1").fetchone()
    return get(row[0]) if row else None
def history():
    with connect() as db: return [{"run_id":i,"version":v,"decision":d} for i,v,d in db.execute("SELECT id,version,decision FROM runs ORDER BY rowid DESC")]
def review(run_id,version,decision):
    if decision not in {"已复核","退回复核"}: raise DomainError("BAD_DECISION","复核状态无效")
    with connect() as db:
        cursor=db.execute("UPDATE runs SET version=version+1,decision=? WHERE id=? AND version=?",(decision,run_id,version))
        if cursor.rowcount!=1:
            if not db.execute("SELECT 1 FROM runs WHERE id=?",(run_id,)).fetchone(): raise DomainError("NOT_FOUND","批次不存在",404)
            raise DomainError("STALE_VERSION","版本已更新，请刷新",409)
    return get(run_id)

def save_shared(share_id,payload):
    # INSERT OR IGNORE：同源重跑复用既有批次，不重复记账；with 事务保证失败回滚、旧版保留
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO sharedcost(id,payload) VALUES (?,?)",(share_id,json.dumps(payload,ensure_ascii=False)))
    return get_shared(share_id)
def get_shared(share_id):
    with connect() as db: row=db.execute("SELECT payload,version,decision FROM sharedcost WHERE id=?",(share_id,)).fetchone()
    if not row: raise DomainError("NOT_FOUND","承接批次不存在",404)
    return {**json.loads(row[0]),"version":row[1],"decision":row[2]}
def latest_shared():
    with connect() as db: row=db.execute("SELECT id FROM sharedcost ORDER BY rowid DESC LIMIT 1").fetchone()
    return get_shared(row[0]) if row else None
def shared_history():
    with connect() as db: return [{"run_id":i,"version":v,"decision":d} for i,v,d in db.execute("SELECT id,version,decision FROM sharedcost ORDER BY rowid DESC")]
def review_shared(share_id,version,decision):
    if decision not in {"已签认","退回承接"}: raise DomainError("BAD_DECISION","签认状态无效")
    with connect() as db:
        cursor=db.execute("UPDATE sharedcost SET version=version+1,decision=? WHERE id=? AND version=?",(decision,share_id,version))
        if cursor.rowcount!=1:
            if not db.execute("SELECT 1 FROM sharedcost WHERE id=?",(share_id,)).fetchone(): raise DomainError("NOT_FOUND","承接批次不存在",404)
            raise DomainError("STALE_VERSION","版本已更新，请刷新",409)
    return get_shared(share_id)
