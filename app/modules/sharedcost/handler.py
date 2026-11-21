from flask import Blueprint,request,jsonify
from app.errors import DomainError
from app.modules.sharedcost import service
from app import store

bp=Blueprint("sharedcost",__name__)

def _payload():
    payload=request.get_json(silent=True) if request.method=="POST" else {}
    if payload is None or not isinstance(payload,dict): raise DomainError("BAD_BODY","请求需要对象")
    return payload

def _raw(payload):
    if "csv" in payload and payload["csv"] is not None:
        if not isinstance(payload["csv"],str): raise DomainError("BAD_CSV","CSV需要文本")
        return payload["csv"].encode()
    return service.load_sample(payload.get("sample",service.SAMPLE))

@bp.route("/api/sharedcost",methods=["GET","POST"])
def preview():
    payload=_payload()
    if request.method=="GET":
        # GET 展示工作台：复用最近批次，无批次时对样例执行一次（幂等）
        return jsonify(store.latest_shared() or service.execute(service.load_sample()))
    raw=_raw(payload)
    return jsonify(service.execute(raw,payload.get("parameters",{})))

@bp.route("/api/sharedcost/runs")
def history():
    return jsonify({"runs":store.shared_history()})

@bp.route("/api/sharedcost/upload",methods=["POST"])
def upload():
    file=request.files.get("file")
    if not file: raise DomainError("NO_FILE","请选择CSV文件")
    return jsonify(service.execute(file.read()))

@bp.route("/api/sharedcost/runs/<share_id>")
def detail(share_id):
    return jsonify(store.get_shared(share_id))

@bp.route("/api/sharedcost/runs/<share_id>/review",methods=["POST"])
def review(share_id):
    p=request.get_json(silent=True) or {}
    if not isinstance(p.get("version"),int): raise DomainError("BAD_VERSION","请提供版本号")
    return jsonify(store.review_shared(share_id,p["version"],p.get("decision")))

@bp.route("/api/sharedcost/runs/<share_id>/archive")
def archive(share_id):
    from flask import current_app
    run=store.get_shared(share_id)
    return current_app.response_class(service.build_archive(run),mimetype="text/csv",
                                      headers={"Content-Disposition":'attachment; filename="sharedcost-evidence.csv"'})
