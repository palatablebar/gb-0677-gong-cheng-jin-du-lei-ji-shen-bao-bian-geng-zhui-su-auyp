const notice=document.getElementById('notice');
const basePath=certificate.kind==='sharedcost'?'/api/sharedcost/runs/':'/api/runs/';
const runPath=certificate.kind==='sharedcost'?'/api/sharedcost':'/api/runs';
const reviewDecision=certificate.kind==='sharedcost'?'已签认':'已复核';
function submitCertificate(path,data){notice.textContent='计量中…';fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}).then(async response=>{const data=await response.json();if(!response.ok)throw new Error(data.message);window.location.reload();}).catch(error=>notice.textContent=error.message);}
document.getElementById('calculate').addEventListener('click',function(){submitCertificate(runPath,{sample:document.getElementById('dataset').value});});
document.getElementById('approve').addEventListener('click',function(){submitCertificate(basePath+certificate.id+'/review',{version:certificate.version,decision:reviewDecision});});
document.getElementById('print').addEventListener('click',()=>window.print());
document.getElementById('attach').addEventListener('click',async()=>{const file=document.getElementById('attachment').files[0];if(!file){notice.textContent='请选择申报文件。';return;}let form=new FormData();form.append('file',file);notice.textContent='导入中…';try{let response=await fetch(certificate.kind==='sharedcost'?'/api/sharedcost/upload':'/api/upload',{method:'POST',body:form});let body=await response.json();if(!response.ok)throw Error(body.message);location.reload();}catch(error){notice.textContent=error.message;}});
document.getElementById('lookup')?.addEventListener('input',function(){document.querySelectorAll('#valuation-rows tr').forEach(row=>row.hidden=!row.textContent.includes(this.value));});
