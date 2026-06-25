# Plano de implementação — stz downloader

Estado atual e próximos passos. O núcleo do app (backend Python + QML + aria2,
extensão Floorp/Chrome, filtro de tipos, modal de confirmação, drawer de
configurações, i18n em 5 idiomas, UI não-bloqueante com QThread) já está
**funcional**. Este documento lista o que falta para "finalizar".

---

## 1. Pendências reais (bloqueiam o "produto completo")

### 1.1 Assets do MSIX
**Problema:** `packaging/msix/AppxManifest.xml` referencia
`Assets/StoreLogo.png`, `Square150x150Logo.png` e `Square44x44Logo.png`, que
não existem — `build.ps1` falha.

**Plano:**
- Estender `scripts/generate_icons.py` (ou criar `generate_msix_assets.py`)
  para gerar os 3 PNGs nos tamanhos exigidos (50x50, 150x150, 44x44) com o mesmo
  ícone da seta.
- Validar o fluxo: `pyinstaller` → `build.ps1` → `.msix` assinado.

### 1.2 i18n da extensão
**Problema:** strings fixas em PT (menu de contexto "Baixar com stz
downloader", popup "Interceptar downloads", status "conectado").

**Plano:**
- Usar o mecanismo nativo `_locales/<lang>/messages.json` do WebExtensions.
- `__MSG_xxx__` no `manifest.json` (nome/descrição) e `chrome.i18n.getMessage()`
  no `background.js`/`popup.js`.
- Idiomas espelhando o app: en, pt, es, de, fr (en como `default_locale`).
- O navegador escolhe pelo locale do usuário automaticamente.

---

## 2. Melhorias oferecidas (opcionais, não bloqueiam)

### 2.1 Velocidade/ETA global no rodapé
- `aria2.getGlobalStat` já existe no client; o servidor expõe via snapshot.
- Adicionar `downloadSpeed`/`numActive` ao payload de `/api/downloads` e mostrar
  no rodapé do QML (velocidade total + nº de ativos). ETA por item = (total −
  baixado) / velocidade.

### 2.2 Abrir pasta / abrir arquivo ao concluir
- Endpoints `POST /api/downloads/{gid}/open` e `/reveal`.
- Backend usa `os.startfile` (Windows) / `xdg-open` / `open` sobre o caminho do
  arquivo (já vem em `files[].path` do aria2).
- QML: botão "📂" no card quando `status === "complete"`.

### 2.3 Persistir a fila entre sessões
- Hoje a fila vive na memória do aria2; ao fechar, downloads em andamento somem.
- aria2 já suporta `--save-session`/`--input-file`. Plano: passar
  `--save-session=%APPDATA%/stz-downloader/session.txt` e
  `--save-session-interval=30` nos `extra_args`, e `--input-file` na inicialização
  do `Aria2Manager` se o arquivo existir.

### 2.4 WebSocket push (em vez de polling de 1s)
- O servidor já expõe `/ws` com broadcast a cada 1s.
- Trocar o `QTimer` do worker por um cliente WebSocket (na thread do worker),
  emitindo `downloads` ao receber. Reduz latência e overhead.

### 2.5 Flash da taskbar (reforço do bring-to-front)
- Quando a janela não puder ganhar foco (foreground lock do Windows), chamar
  `FlashWindowEx` via `ctypes` para piscar na barra de tarefas.

### 2.6 Agrupar múltiplos pendings
- Hoje o modal mostra 1 por vez. Alternativa: lista com checkbox + "Baixar
  todos" / "Cancelar todos" quando `pending.length > 1`.

### 2.7 RTL (árabe/hebraico)
- `LayoutMirroring.enabled` + `LayoutMirroring.childrenInherit` quando o idioma
  for RTL. Requer revisão dos `anchors` manuais.

---

## 3. Para "finalizar" (qualidade / distribuição)

- **Empacotamento end-to-end:** documentar e testar `pyinstaller` + `build.ps1`;
  embutir `aria2c.exe` no bundle (hoje é baixado via script).
- **Assinatura:** instruções de import do `.cer` (self-signed) já no README;
  avaliar certificado real se for distribuir amplamente.
- **Testes:** `pytest` para o client aria2 (mock RPC) e para os endpoints
  (FastAPI `TestClient`); smoke test do filtro da extensão.
- **CI (GitHub Actions):** lint (`ruff`), `pytest`, build do `.msix` em tag.
- **Conformidade GPL:** confirmar que `LICENSE` do aria2 + `SOURCE.md` vão no
  bundle distribuído (mera agregação — já documentado).
- **Autostart opcional:** iniciar a bridge no login (atalho em Startup / chave
  de registro), para a extensão sempre achar a bridge no ar.
- **Auto-update:** checagem de versão via GitHub Releases (opcional).
- **Ícone do app/janela:** definir ícone da janela QML e do executável.

---

## Prioridade sugerida

1. **Assets do MSIX** + **i18n da extensão** (lacunas reais).
2. **Persistência da fila** (2.3) e **abrir pasta/arquivo** (2.2) — alto valor,
   baixo custo.
3. **ETA/velocidade global** (2.1) e **WebSocket push** (2.4).
4. Demais opcionais conforme necessidade.
