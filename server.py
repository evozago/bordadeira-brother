#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server.py — Painel + API REST para a bordadeira Brother.

Roda um servidor local. Abre uma página de controle no navegador E expõe
uma API REST genérica que QUALQUER sistema (PHP, Node, Python, etc.) pode
chamar para enviar/gerenciar bordados.

Uso:
    python3 server.py
    python3 server.py --ip 192.168.1.120 --port 8765

API REST:
    GET  /api/status                 -> {info, status}  (dados + espaço + arquivos)
    GET  /api/files                  -> {files: [...]}
    POST /api/send?name=ARQ.pes      -> body = bytes do .pes  -> {ok, http}
         (ou cabeçalho  X-Filename: ARQ.pes)
"""

import argparse
import json
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import brother_machine as bm

MACHINE_IP = "192.168.1.120"

PAGE = r"""<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Painel da Bordadeira</title>
<style>
 :root{--bg:#0f1115;--card:#1a1d24;--ln:#2a2f3a;--tx:#e8eaed;--mut:#9aa0ab;--ac:#4f8cff;--ok:#39c07a;--er:#ff5d5d}
 *{box-sizing:border-box} body{margin:0;font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--tx)}
 .wrap{max-width:860px;margin:0 auto;padding:24px}
 h1{font-size:20px;margin:0 0 4px} .sub{color:var(--mut);font-size:13px;margin-bottom:20px}
 .card{background:var(--card);border:1px solid var(--ln);border-radius:14px;padding:18px;margin-bottom:16px}
 .row{display:flex;gap:16px;flex-wrap:wrap} .row>.card{flex:1;min-width:240px}
 .k{color:var(--mut);font-size:12px} .v{font-size:15px;font-weight:600;margin-top:2px}
 .bar{height:12px;background:#11141a;border-radius:8px;overflow:hidden;margin-top:8px}
 .bar>i{display:block;height:100%;background:linear-gradient(90deg,#4f8cff,#39c07a)}
 .files{list-style:none;margin:8px 0 0;padding:0;max-height:220px;overflow:auto}
 .files li{padding:8px 10px;border:1px solid var(--ln);border-radius:8px;margin-bottom:6px;font-size:14px;display:flex;justify-content:space-between}
 button{background:var(--ac);color:#fff;border:0;border-radius:9px;padding:10px 16px;font-size:14px;font-weight:600;cursor:pointer}
 button.ghost{background:transparent;border:1px solid var(--ln);color:var(--tx)}
 button:disabled{opacity:.5;cursor:default}
 .drop{border:2px dashed var(--ln);border-radius:12px;padding:26px;text-align:center;color:var(--mut);cursor:pointer}
 .drop.hot{border-color:var(--ac);color:var(--tx)}
 .q{list-style:none;margin:14px 0 0;padding:0}
 .q li{display:flex;align-items:center;gap:10px;padding:8px 10px;border:1px solid var(--ln);border-radius:8px;margin-bottom:6px;font-size:14px}
 .tag{font-size:12px;padding:2px 8px;border-radius:20px;margin-left:auto}
 .tag.wait{background:#2a2f3a;color:var(--mut)} .tag.go{background:#23314d;color:var(--ac)}
 .tag.ok{background:#16361f;color:var(--ok)} .tag.er{background:#3a1717;color:var(--er)}
 .muted{color:var(--mut);font-size:12px} .err{color:var(--er)} a{color:var(--ac)}
</style></head><body><div class="wrap">
 <h1>🧵 Painel da Bordadeira</h1>
 <div class="sub" id="sub">conectando...</div>
 <div class="row">
   <div class="card"><div class="k">Maquina</div><div class="v" id="mname">—</div><div class="muted" id="mmeta">—</div></div>
   <div class="card"><div class="k">Espaco da memoria</div><div class="v" id="space">—</div>
     <div class="bar"><i id="barfill" style="width:0%"></i></div><div class="muted" id="spacepct">—</div></div>
 </div>
 <div class="card">
   <div style="display:flex;justify-content:space-between;align-items:center">
     <strong>Arquivos na maquina</strong><button class="ghost" onclick="refresh()">↻ Atualizar</button></div>
   <ul class="files" id="files"></ul>
 </div>
 <div class="card">
   <strong>Enviar bordados (.pes)</strong>
   <div class="muted" style="margin:4px 0 12px">Arraste arquivos aqui ou clique para escolher. Pode selecionar varios.</div>
   <div class="drop" id="drop">📁 Solte os .pes aqui ou clique para escolher</div>
   <input type="file" id="file" accept=".pes" multiple hidden>
   <ul class="q" id="queue"></ul>
   <div style="margin-top:12px;display:flex;gap:10px">
     <button id="send" onclick="sendAll()" disabled>Enviar fila</button>
     <button class="ghost" onclick="clearQueue()">Limpar</button></div>
 </div>
 <div class="muted">Painel local • fala direto com a maquina pela rede • sem app, sem nuvem</div>
</div>
<script>
let queue=[]; const $=s=>document.querySelector(s);
function human(n){if(n>=1048576)return (n/1048576).toFixed(2)+' MB';if(n>=1024)return (n/1024).toFixed(0)+' KB';return n+' B';}
async function refresh(){
  $('#sub').textContent='atualizando...';
  try{
    const r=await fetch('/api/status'); const d=await r.json();
    if(d.error)throw new Error(d.error);
    $('#mname').textContent=d.info.name||'Bordadeira';
    $('#mmeta').textContent=`serie ${d.info.serial} • firmware ${d.info.version} • area ${(d.info.features.embwidth/100)}x${(d.info.features.embheight/100)} cm`;
    $('#space').textContent=human(d.status.free)+' livres de '+human(d.status.total);
    const pct=d.status.total?Math.round(d.status.used/d.status.total*100):0;
    $('#barfill').style.width=pct+'%';
    $('#spacepct').textContent=pct+'% usado • limite por arquivo: '+human(d.info.features.postsize);
    const ul=$('#files');ul.innerHTML='';
    if(!d.status.files.length)ul.innerHTML='<li class="muted">nenhum arquivo na maquina</li>';
    d.status.files.forEach(f=>{const li=document.createElement('li');li.innerHTML='<span>🧵 '+f+'</span>';ul.appendChild(li);});
    $('#sub').textContent='conectado a '+d.ip;
  }catch(e){$('#sub').innerHTML='<span class="err">sem conexao com a maquina ('+e.message+'). Ligada e na mesma rede?</span>';}
}
const drop=$('#drop'),fileInput=$('#file');
drop.onclick=()=>fileInput.click(); fileInput.onchange=e=>addFiles(e.target.files);
['dragover','dragenter'].forEach(ev=>drop.addEventListener(ev,e=>{e.preventDefault();drop.classList.add('hot');}));
['dragleave','drop'].forEach(ev=>drop.addEventListener(ev,e=>{e.preventDefault();drop.classList.remove('hot');}));
drop.addEventListener('drop',e=>addFiles(e.dataTransfer.files));
function addFiles(list){[...list].forEach(f=>{const rd=new FileReader();rd.onload=()=>{queue.push({name:f.name,b64:rd.result.split(',')[1],state:'wait'});render();};rd.readAsDataURL(f);});}
function clearQueue(){queue=[];render();}
function render(){const ul=$('#queue');ul.innerHTML='';
  queue.forEach(q=>{const li=document.createElement('li');
    const t={wait:['wait','na fila'],go:['go','enviando...'],ok:['ok','enviado ✓'],er:['er','erro ✗']}[q.state];
    li.innerHTML='<span>📄 '+q.name+'</span><span class="tag '+t[0]+'">'+t[1]+'</span>';ul.appendChild(li);});
  $('#send').disabled=queue.length===0||queue.every(q=>q.state==='ok');}
async function sendAll(){$('#send').disabled=true;
  for(const q of queue){if(q.state==='ok')continue;q.state='go';render();
    try{const r=await fetch('/api/send?name='+encodeURIComponent(q.name),{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:Uint8Array.from(atob(q.b64),c=>c.charCodeAt(0))});
      const d=await r.json();q.state=d.ok?'ok':'er';}catch(e){q.state='er';}render();}
  refresh();}
refresh();setInterval(refresh,15000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = urlparse(self.path)
        if p.path == "/":
            data = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif p.path == "/api/status":
            try:
                self._json({"ip": MACHINE_IP, "info": bm.info(MACHINE_IP), "status": bm.status(MACHINE_IP)})
            except Exception as e:
                self._json({"error": str(e)})
        elif p.path == "/api/files":
            try:
                self._json({"files": bm.status(MACHINE_IP)["files"]})
            except Exception as e:
                self._json({"error": str(e)})
        else:
            self.send_error(404)

    def do_POST(self):
        p = urlparse(self.path)
        if p.path == "/api/send":
            qs = parse_qs(p.query)
            name = self.headers.get("X-Filename") or (qs.get("name") or ["bordado.pes"])[0]
            n = int(self.headers.get("Content-Length", 0))
            pes = self.rfile.read(n)
            try:
                ok, http_status = bm.send(MACHINE_IP, pes, name)
                self._json({"ok": ok, "http": http_status, "name": name})
            except Exception as e:
                self._json({"ok": False, "error": str(e)})
        else:
            self.send_error(404)


def main():
    global MACHINE_IP
    ap = argparse.ArgumentParser()
    ap.add_argument("--ip", default=MACHINE_IP)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    MACHINE_IP = args.ip
    url = f"http://localhost:{args.port}"
    print(f"Painel + API da bordadeira em: {url}")
    print(f"Maquina: {MACHINE_IP}  |  Ctrl+C para parar")
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
