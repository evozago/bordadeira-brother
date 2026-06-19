#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server.py — Painel + API REST para bordadeiras Brother (v2).

Recursos:
  - Multi-máquina (machines.json)
  - Monitorar: dados, espaço livre, arquivos na memória
  - Enviar .pes (com checagem de espaço e nome padronizado)
  - Converter automaticamente DST/EXP/JEF/... para PES (se pyembroidery instalado)
  - Catálogo: pasta local de bordados com botão enviar
  - Histórico de envios

Uso:
    python3 server.py                 # abre http://localhost:8765
    python3 server.py --port 8765

API REST (resumo — veja README):
    GET  /api/machines
    GET  /api/status?ip=...
    GET  /api/catalog
    GET  /api/history
    POST /api/send?ip=...&name=ARQ.pes        (corpo = bytes do arquivo)
    POST /api/send_catalog?ip=...&file=NOME   (envia item do catálogo)
"""

import argparse
import json
import os
import re
import time
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import brother_machine as bm
import convert

BASE = os.path.dirname(os.path.abspath(__file__))
MACHINES_FILE = os.path.join(BASE, "machines.json")
HISTORY_FILE = os.path.join(BASE, "history.json")
DESIGNS_DIR = os.path.join(BASE, "designs")


# ---------------- config / estado ----------------
def load_machines():
    if not os.path.isfile(MACHINES_FILE):
        data = [{"name": "Bordadeira", "ip": "192.168.1.120"}]
        with open(MACHINES_FILE, "w") as f:
            json.dump(data, f, indent=2)
    with open(MACHINES_FILE) as f:
        return json.load(f)


def default_ip():
    m = load_machines()
    return m[0]["ip"] if m else "192.168.1.120"


def log_history(entry):
    hist = read_history(10000)
    entry["time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    hist.insert(0, entry)
    with open(HISTORY_FILE, "w") as f:
        json.dump(hist[:500], f, indent=2, ensure_ascii=False)


def read_history(limit=50):
    if not os.path.isfile(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE) as f:
            return json.load(f)[:limit]
    except Exception:
        return []


def sanitize(name):
    name = os.path.basename(name).strip().replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9._-]", "", name) or "bordado.pes"


def catalog():
    os.makedirs(DESIGNS_DIR, exist_ok=True)
    out = []
    for fn in sorted(os.listdir(DESIGNS_DIR)):
        p = os.path.join(DESIGNS_DIR, fn)
        if os.path.isfile(p) and convert.is_supported(fn):
            out.append({"name": fn, "size": os.path.getsize(p),
                        "ext": os.path.splitext(fn)[1].lower()})
    return out


def process_and_send(ip, raw, name):
    """Converte (se preciso), checa espaço, envia e registra histórico."""
    name = sanitize(name)
    pes, final = convert.to_pes(raw, name)
    final = sanitize(final)
    # checagem de espaço e limite
    try:
        nfo = bm.info(ip)
        st = bm.status(ip)
        limit = nfo.get("features", {}).get("postsize", 3000000)
        if len(pes) > limit:
            raise RuntimeError(f"Arquivo {len(pes)}B excede o limite por arquivo ({limit}B).")
        if len(pes) > st["free"]:
            raise RuntimeError(f"Espaco insuficiente: livre {st['free']}B, precisa {len(pes)}B.")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Sem conexao com a maquina: {e}")
    ok, http_status = bm.send(ip, pes, final)
    log_history({"machine": ip, "name": final, "size": len(pes),
                 "ok": ok, "http": http_status})
    return {"ok": ok, "http": http_status, "name": final, "size": len(pes)}


# ---------------- página web ----------------
PAGE = r"""<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Bordadeira</title>
<style>
 :root{--bg:#0f1115;--card:#1a1d24;--ln:#2a2f3a;--tx:#e8eaed;--mut:#9aa0ab;--ac:#4f8cff;--ok:#39c07a;--er:#ff5d5d}
 *{box-sizing:border-box}body{margin:0;font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--tx)}
 .wrap{max-width:920px;margin:0 auto;padding:24px}
 h1{font-size:20px;margin:0 0 4px}.sub{color:var(--mut);font-size:13px;margin-bottom:16px}
 .card{background:var(--card);border:1px solid var(--ln);border-radius:14px;padding:18px;margin-bottom:16px}
 .row{display:flex;gap:16px;flex-wrap:wrap}.row>.card{flex:1;min-width:240px}
 .k{color:var(--mut);font-size:12px}.v{font-size:15px;font-weight:600;margin-top:2px}
 .bar{height:12px;background:#11141a;border-radius:8px;overflow:hidden;margin-top:8px}.bar>i{display:block;height:100%;background:linear-gradient(90deg,#4f8cff,#39c07a)}
 ul{list-style:none;margin:8px 0 0;padding:0}
 li.item{padding:8px 10px;border:1px solid var(--ln);border-radius:8px;margin-bottom:6px;font-size:14px;display:flex;align-items:center;gap:10px}
 button{background:var(--ac);color:#fff;border:0;border-radius:9px;padding:9px 14px;font-size:14px;font-weight:600;cursor:pointer}
 button.ghost{background:transparent;border:1px solid var(--ln);color:var(--tx)}
 button.sm{padding:5px 10px;font-size:13px;margin-left:auto}
 button:disabled{opacity:.5;cursor:default}
 select{background:#11141a;color:var(--tx);border:1px solid var(--ln);border-radius:8px;padding:8px}
 .drop{border:2px dashed var(--ln);border-radius:12px;padding:22px;text-align:center;color:var(--mut);cursor:pointer}
 .drop.hot{border-color:var(--ac);color:var(--tx)}
 .tag{font-size:12px;padding:2px 8px;border-radius:20px;margin-left:auto}
 .tag.wait{background:#2a2f3a;color:var(--mut)}.tag.go{background:#23314d;color:var(--ac)}
 .tag.ok{background:#16361f;color:var(--ok)}.tag.er{background:#3a1717;color:var(--er)}
 .muted{color:var(--mut);font-size:12px}.err{color:var(--er)}a{color:var(--ac)}
 h3{font-size:15px;margin:0 0 6px}
</style></head><body><div class="wrap">
 <h1>🧵 Gerenciador da Bordadeira</h1>
 <div class="sub" id="sub">conectando...</div>

 <div class="card" style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
   <span class="k">Maquina:</span>
   <select id="machine" onchange="refresh()"></select>
   <button class="ghost" onclick="refresh()">↻ Atualizar</button>
 </div>

 <div class="row">
   <div class="card"><div class="k">Maquina</div><div class="v" id="mname">—</div><div class="muted" id="mmeta">—</div></div>
   <div class="card"><div class="k">Memoria</div><div class="v" id="space">—</div>
     <div class="bar"><i id="barfill" style="width:0%"></i></div><div class="muted" id="spacepct">—</div></div>
 </div>

 <div class="card">
   <div style="display:flex;justify-content:space-between"><h3>Arquivos na maquina</h3></div>
   <ul id="files"></ul>
   <div class="muted">Excluir/renomear na maquina ainda nao disponivel (depende de captura). Veja README.</div>
 </div>

 <div class="card">
   <h3>Enviar (.pes, .dst, .exp, .jef...)</h3>
   <div class="muted" style="margin:2px 0 10px">Formatos diferentes de PES sao convertidos automaticamente. Limite por arquivo: <span id="lim">—</span>.</div>
   <div class="drop" id="drop">📁 Solte arquivos aqui ou clique para escolher</div>
   <input type="file" id="file" multiple hidden>
   <ul id="queue"></ul>
   <div style="margin-top:10px;display:flex;gap:10px"><button id="send" onclick="sendAll()" disabled>Enviar fila</button><button class="ghost" onclick="queue=[];render()">Limpar</button></div>
 </div>

 <div class="card">
   <h3>Catalogo</h3>
   <div class="muted" style="margin-bottom:8px">Pasta de bordados no computador. Coloque arquivos em <code id="cdir">designs/</code> e atualize.</div>
   <ul id="catalog"></ul>
 </div>

 <div class="card"><h3>Historico de envios</h3><ul id="history"></ul></div>
 <div class="muted">Painel local • fala direto com a maquina • sem app, sem nuvem</div>
</div>
<script>
let queue=[]; const $=s=>document.querySelector(s);
function human(n){if(n>=1048576)return (n/1048576).toFixed(2)+' MB';if(n>=1024)return (n/1024).toFixed(0)+' KB';return n+' B';}
function ip(){return $('#machine').value;}

async function loadMachines(){
  const d=await (await fetch('/api/machines')).json();
  const sel=$('#machine');sel.innerHTML='';
  d.machines.forEach(m=>{const o=document.createElement('option');o.value=m.ip;o.textContent=m.name+' ('+m.ip+')';sel.appendChild(o);});
}
async function refresh(){
  $('#sub').textContent='atualizando...';
  try{
    const d=await (await fetch('/api/status?ip='+encodeURIComponent(ip()))).json();
    if(d.error)throw new Error(d.error);
    $('#mname').textContent=d.info.name||'Bordadeira';
    $('#mmeta').textContent='serie '+d.info.serial+' • fw '+d.info.version+' • area '+(d.info.features.embwidth/100)+'x'+(d.info.features.embheight/100)+' cm';
    $('#space').textContent=human(d.status.free)+' livres de '+human(d.status.total);
    const pct=d.status.total?Math.round(d.status.used/d.status.total*100):0;
    $('#barfill').style.width=pct+'%';
    $('#spacepct').textContent=pct+'% usado';
    $('#lim').textContent=human(d.info.features.postsize);
    const ul=$('#files');ul.innerHTML='';
    if(!d.status.files.length)ul.innerHTML='<li class="muted">vazia</li>';
    d.status.files.forEach(f=>{const li=document.createElement('li');li.className='item';li.innerHTML='<span>🧵 '+f+'</span>';ul.appendChild(li);});
    $('#sub').textContent='conectado a '+d.ip;
  }catch(e){$('#sub').innerHTML='<span class="err">sem conexao ('+e.message+'). Ligada e na mesma rede?</span>';}
  loadCatalog();loadHistory();
}
async function loadCatalog(){
  const d=await (await fetch('/api/catalog')).json();
  $('#cdir').textContent=d.dir;
  const ul=$('#catalog');ul.innerHTML='';
  if(!d.files.length){ul.innerHTML='<li class="muted">nenhum arquivo na pasta designs/</li>';return;}
  d.files.forEach(f=>{const li=document.createElement('li');li.className='item';
    li.innerHTML='<span>📄 '+f.name+'</span><span class="muted">'+human(f.size)+'</span>'+
      '<button class="sm" onclick="sendCatalog(this,\''+encodeURIComponent(f.name)+'\')">Enviar</button>';
    ul.appendChild(li);});
}
async function loadHistory(){
  const d=await (await fetch('/api/history')).json();
  const ul=$('#history');ul.innerHTML='';
  if(!d.history.length){ul.innerHTML='<li class="muted">sem envios ainda</li>';return;}
  d.history.slice(0,15).forEach(h=>{const li=document.createElement('li');li.className='item';
    li.innerHTML='<span>'+(h.ok?'✓':'✗')+' '+h.name+'</span><span class="muted">'+h.time+' • '+human(h.size||0)+'</span>';
    ul.appendChild(li);});
}
async function sendCatalog(btn,fileEnc){
  btn.disabled=true;btn.textContent='...';
  try{const d=await (await fetch('/api/send_catalog?ip='+encodeURIComponent(ip())+'&file='+fileEnc,{method:'POST'})).json();
    btn.textContent=d.ok?'enviado ✓':'erro ✗';}catch(e){btn.textContent='erro ✗';}
  refresh();
}
const drop=$('#drop'),fileInput=$('#file');
drop.onclick=()=>fileInput.click();fileInput.onchange=e=>addFiles(e.target.files);
['dragover','dragenter'].forEach(ev=>drop.addEventListener(ev,e=>{e.preventDefault();drop.classList.add('hot');}));
['dragleave','drop'].forEach(ev=>drop.addEventListener(ev,e=>{e.preventDefault();drop.classList.remove('hot');}));
drop.addEventListener('drop',e=>addFiles(e.dataTransfer.files));
function addFiles(list){[...list].forEach(f=>{const rd=new FileReader();rd.onload=()=>{queue.push({name:f.name,b64:rd.result.split(',')[1],state:'wait'});render();};rd.readAsDataURL(f);});}
function render(){const ul=$('#queue');ul.innerHTML='';
  queue.forEach(q=>{const li=document.createElement('li');li.className='item';
    const t={wait:['wait','na fila'],go:['go','enviando...'],ok:['ok','enviado ✓'],er:['er','erro ✗']}[q.state];
    li.innerHTML='<span>📄 '+q.name+'</span><span class="tag '+t[0]+'">'+t[1]+'</span>';ul.appendChild(li);});
  $('#send').disabled=queue.length===0||queue.every(q=>q.state==='ok');}
async function sendAll(){$('#send').disabled=true;
  for(const q of queue){if(q.state==='ok')continue;q.state='go';render();
    try{const r=await fetch('/api/send?ip='+encodeURIComponent(ip())+'&name='+encodeURIComponent(q.name),{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:Uint8Array.from(atob(q.b64),c=>c.charCodeAt(0))});
      const d=await r.json();q.state=d.ok?'ok':'er';if(!d.ok&&d.error)q.err=d.error;}catch(e){q.state='er';}render();}
  refresh();}
loadMachines().then(refresh);setInterval(refresh,20000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = urlparse(self.path)
        q = parse_qs(p.query)
        if p.path == "/":
            data = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif p.path == "/api/machines":
            self._json({"machines": load_machines()})
        elif p.path == "/api/status":
            ip = (q.get("ip") or [default_ip()])[0]
            try:
                self._json({"ip": ip, "info": bm.info(ip), "status": bm.status(ip)})
            except Exception as e:
                self._json({"error": str(e)})
        elif p.path == "/api/catalog":
            self._json({"dir": DESIGNS_DIR, "files": catalog()})
        elif p.path == "/api/history":
            self._json({"history": read_history(50)})
        else:
            self.send_error(404)

    def do_POST(self):
        p = urlparse(self.path)
        q = parse_qs(p.query)
        ip = (q.get("ip") or [default_ip()])[0]
        if p.path == "/api/send":
            name = self.headers.get("X-Filename") or (q.get("name") or ["bordado.pes"])[0]
            n = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(n)
            try:
                self._json(process_and_send(ip, raw, name))
            except Exception as e:
                self._json({"ok": False, "error": str(e)})
        elif p.path == "/api/send_catalog":
            fn = sanitize((q.get("file") or [""])[0])
            path = os.path.join(DESIGNS_DIR, fn)
            if not os.path.isfile(path):
                self._json({"ok": False, "error": "arquivo nao encontrado no catalogo"})
                return
            try:
                self._json(process_and_send(ip, open(path, "rb").read(), fn))
            except Exception as e:
                self._json({"ok": False, "error": str(e)})
        elif p.path in ("/api/delete", "/api/rename"):
            self._json({"ok": False, "error": "Operacao ainda nao mapeada na maquina (precisa de captura)."}, 501)
        else:
            self.send_error(404)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    load_machines()
    os.makedirs(DESIGNS_DIR, exist_ok=True)
    url = f"http://localhost:{args.port}"
    print(f"Gerenciador da bordadeira em: {url}")
    print(f"Maquinas: {MACHINES_FILE}  |  Catalogo: {DESIGNS_DIR}  |  Ctrl+C para parar")
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
