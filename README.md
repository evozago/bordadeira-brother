# bordadeira-brother

Controle e integração de **bordadeiras Brother** (linha Innov-is / WLAN, ex.:
**BP1530L**) pela **rede local** — sem o app Artspira, sem o programa Design
Database Transfer e sem nuvem.

Inclui:

- **Painel web** local para monitorar e enviar bordados (`server.py`).
- **API REST** genérica para integrar com qualquer sistema (PHP, Node, Python…).
- **CLI** para automação/scripts (`send_cli.py`).
- **Biblioteca** Python do protocolo (`brother_machine.py`).
- Documentação do protocolo descoberto por engenharia reversa (`PROTOCOL.md`).

Só precisa de **Python 3** (biblioteca padrão, nada para instalar).

> ⚠️ Projeto não-oficial, sem vínculo com a Brother. Sem garantia. Use na sua
> própria máquina, por sua conta e risco.

## Requisitos

- A bordadeira ligada e na **mesma rede** que o computador.
- Saber o **IP da máquina** (padrão deste projeto: `192.168.1.120`).

## Início rápido

### Painel web
```bash
python3 server.py            # abre http://localhost:8765 no navegador
python3 server.py --ip 192.168.1.130 --port 8765
```

No painel você vê os dados da máquina, o espaço livre, os arquivos já na
memória e pode arrastar vários `.pes` para enviar em fila.

### Linha de comando
```bash
python3 send_cli.py --info               # mostra status e arquivos
python3 send_cli.py desenho.pes          # envia um bordado
python3 send_cli.py desenho.pes --name PEDIDO123.pes
```

## API REST (para o seu sistema)

Suba o servidor (`python3 server.py`) e chame de qualquer linguagem:

| Método | Rota | Descrição |
|-------|------|-----------|
| GET | `/api/status` | Dados da máquina + espaço + lista de arquivos |
| GET | `/api/files`  | Só a lista de arquivos na máquina |
| POST | `/api/send?name=ARQ.pes` | Envia um `.pes` (corpo = bytes do arquivo) |

### Exemplos

**curl**
```bash
curl --data-binary @desenho.pes \
  "http://localhost:8765/api/send?name=PEDIDO123.pes"
```

**PHP**
```php
$pes = file_get_contents('desenho.pes');
$ch = curl_init('http://localhost:8765/api/send?name=PEDIDO123.pes');
curl_setopt_array($ch, [CURLOPT_POST=>true, CURLOPT_POSTFIELDS=>$pes,
  CURLOPT_RETURNTRANSFER=>true, CURLOPT_HTTPHEADER=>['Content-Type: application/octet-stream']]);
echo curl_exec($ch);
```

**Node.js**
```js
import { readFileSync } from 'fs';
await fetch('http://localhost:8765/api/send?name=PEDIDO123.pes', {
  method: 'POST', headers: { 'Content-Type': 'application/octet-stream' },
  body: readFileSync('desenho.pes')
}).then(r => r.json()).then(console.log);
```

**Python**
```python
import requests
requests.post("http://localhost:8765/api/send",
              params={"name": "PEDIDO123.pes"},
              data=open("desenho.pes", "rb").read())
```

## Como funciona

A máquina expõe um servidor HTTPS local com a API `pedxml`. O envio é um
`POST multipart` para `/sewing/sewing.cgi`. Detalhes completos em
[`PROTOCOL.md`](PROTOCOL.md).

## Arquivos

| Arquivo | Função |
|--------|--------|
| `brother_machine.py` | Biblioteca do protocolo (info / status / send) |
| `server.py` | Painel web + API REST |
| `send_cli.py` | Envio por linha de comando |
| `PROTOCOL.md` | Documentação do protocolo |

## Limitações / próximos passos

- **Enviar** e **listar/monitorar** funcionam. **Apagar/editar** arquivos na
  máquina ainda não foi mapeado (precisaria de nova captura do software oficial).
- Testado na **BP1530L** (firmware 1.73). Outros modelos WLAN da Brother usam o
  mesmo padrão, mas podem variar.

## Licença

MIT — veja [`LICENSE`](LICENSE).
