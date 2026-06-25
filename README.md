# stz downloader

Um gerenciador de downloads moderno, estilo IDM, com backend em **Python** +
interface em **QML (PySide6)** e o motor de download **aria2**. Inclui uma
extensão de navegador (Manifest V3) que intercepta downloads e os repassa ao
aria2 — a sensação "IDM".

## Arquitetura

```
Extensão (Chrome/Firefox)  ──HTTP──►  Bridge FastAPI (127.0.0.1:8765)
                                          │  JSON-RPC
UI QML (PySide6)  ──HTTP/WS──►  Bridge ───►  aria2c (subprocesso, :6800)
```

- `src/stz_downloader/aria2/`  — gerência do processo `aria2c` + cliente JSON-RPC
- `src/stz_downloader/server/` — ponte FastAPI (REST + WebSocket) usada pela UI e pela extensão
- `src/stz_downloader/ui/`     — UI em QML e o backend que a alimenta
- `extension/`                 — extensão MV3
- `third_party/aria2/`         — binário do aria2 (GPL, baixado à parte) + licença
- `packaging/msix/`            — empacotamento MSIX self-signed

## Desenvolvimento

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
python scripts/fetch_aria2.py      # baixa aria2c.exe + licença GPL
python -m stz_downloader           # sobe a bridge + UI
python -m stz_downloader --headless  # só a bridge (para testar a extensão)
```

### Extensão

A bridge precisa estar rodando (`python -m stz_downloader` ou
`--headless`). O botão da extensão mostra se está conectada.

Gere os ícones uma vez: `python scripts/generate_icons.py`.

**Firefox / Floorp (Ablaze):**
1. Copie `manifest.firefox.json` por cima de `manifest.json` (o Firefox usa
   `background.scripts`; o Chrome usa `service_worker`):
   ```bash
   cp extension/manifest.firefox.json extension/manifest.json
   ```
   (ou rode `python scripts/build_extension.py firefox`)
2. Abra `about:debugging#/runtime/this-firefox` → **Carregar extensão
   temporária** → selecione qualquer arquivo dentro de `extension/`.
3. Clique no ícone da extensão → **Permissões** → permita acesso a todos os
   sites. No Firefox MV3 as permissões de host são opcionais; sem isso os
   cookies não são repassados e downloads autenticados podem falhar.

> Extensão temporária some ao fechar o navegador. Para fixar, é preciso
> assinar (AMO) ou usar uma build que aceite extensões não assinadas.

**Chrome / Edge / Brave:**
1. Garanta o `manifest.json` na variante Chrome
   (`python scripts/build_extension.py chrome`).
2. `chrome://extensions` → ative **Modo desenvolvedor** → **Carregar sem
   compactar** → selecione a pasta `extension/`.

## Configuração

Padrões em `pyproject.toml` sob `[tool.stz-downloader.*]`. Sobrescreva em
`%APPDATA%/stz-downloader/config.toml`:

```toml
[aria2]
rpc_port = 6900

[downloads]
directory = "D:/Downloads"
```

## Empacotamento (MSIX self-signed)

```powershell
pip install ".[packaging]"
pyinstaller --noconfirm --windowed --name stz-downloader src/stz_downloader/__main__.py
powershell -ExecutionPolicy Bypass -File packaging/msix/build.ps1
```

O MSIX é assinado com um certificado self-signed. Para instalar em outra
máquina, importe `dist/stz-downloader-dev.cer` em **Trusted People** antes de
abrir o `.msix`.

## Licenças

Código deste projeto: MIT. O binário do **aria2** é GPLv2+ e é usado como
processo externo (mera agregação) — veja `third_party/aria2/SOURCE.md`.
