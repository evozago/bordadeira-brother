# Protocolo local da bordadeira Brother (engenharia reversa)

Documentação do protocolo usado pelo software **Design Database Transfer** da
Brother para enviar bordados pela rede local, obtido por captura de tráfego
(mitmproxy) entre o programa e uma **Innov-is BP1530L** (firmware 1.73).

> Não-oficial. Sem garantia. Use por sua conta e risco, na sua própria máquina.

## Visão geral

- Transporte: **HTTPS** na porta **443**.
- A máquina usa um **certificado auto-assinado** (CN do tipo `56;2;1;1.73.local`)
  e **não valida** o cliente — o cliente também ignora o certificado.
- Servidor embarcado: `debut/1.20`.
- A máquina expõe `/info` (JSON) e o endpoint `/sewing/sewing.cgi`.

## 1. Identificação — `GET /info`

```json
{
  "model": 56, "type": 2, "oem": 1, "version": "1.73",
  "machine-id": "5675809173", "serial": "B5P277522", "name": "BROTHERBP1530L",
  "apis": { "pedxml": {"version": 1}, "monitoring": {"version": 0},
            "camera": {"version": 0}, "streaming": {"version": 0} },
  "features": { "embwidth": 1600, "embheight": 2600, "needles": 1, "postsize": 3000000 }
}
```

- `pedxml.version: 1` → API de transferência ativa (PE-DESIGN XML).
- `postsize` → tamanho máximo de um arquivo enviado (≈3 MB).
- `embwidth`/`embheight` → área de bordado em 0,1 mm (1600 = 160 mm).

## 2. Abrir sessão / status — `POST /sewing/sewing.cgi`

Cabeçalhos: `User-Agent: Design Database Transfer`, `Accept-Language: 1046`,
`Cache-Control: no-cache`, `Content-Type: application/x-www-form-urlencoded`.

Corpo:

```
req_sessionid=0&req_appid=23&req_appver=1.2.0&req_appstate=2
```

Resposta (XML, `application/octet-stream`):

```xml
<respose_info>
  <respose_status><error_code>0</error_code></respose_status>
  <term_info><session_id>0</session_id></term_info>
  <data_path>
    <upload_path>/sewing/dataupl.cgi</upload_path>
    <upload_size>4194304</upload_size>
    <upload_freesize>4133845</upload_freesize>
  </data_path>
  <files>
    <file_name>32769.PES</file_name>
  </files>
</respose_info>
```

- `error_code` 0 = ok.
- `upload_size` / `upload_freesize` = memória total / livre (bytes).
- `<files>` = arquivos atualmente na máquina (nomes atribuídos por ela).
- Esta mesma chamada serve para **consultar status** e **listar arquivos**.

## 3. Enviar bordado — `POST /sewing/sewing.cgi` (multipart)

`Content-Type: multipart/form-data;boundary=---------------------------XXXXXXXXXXXX`

Duas partes:

**Parte 1** — parâmetros:
```
Content-Disposition:form-data;name="req_parameter";filename="req_parameter"
Content-Type:application/x-www-form-urlencoded

req_sessionid=0&req_appid=23&req_appver=100&req_appstate=3
```

**Parte 2** — o arquivo:
```
Content-Disposition:form-data;name="myfile";filename="qualquer_nome.pes"
Content-Type:application/octet-stream

<bytes do arquivo .pes — começa com "#PES">
```

Resposta de sucesso: **HTTP 204** (sem corpo). A máquina atribui o nome final
(ex.: `32770.PES`), confirmável repetindo a chamada de status (passo 2).

## Observações

- `appstate`: `2` = status/handshake, `3` = enviando arquivo.
- O `filename` da parte 2 é ignorado pela máquina (ela renomeia).
- **Apagar/editar arquivos na máquina**: ainda não mapeado nesta captura.
  Exigiria capturar o tráfego de uma operação de exclusão no software oficial
  (se ele oferecer) para descobrir o `appstate`/endpoint correspondente.
