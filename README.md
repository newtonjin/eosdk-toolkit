# EOSLANKit

Ferramenta universal com GUI para jogos **Unreal Engine + Steam + Epic Online Services (EOS)** rodarem em **LAN/offline** sem depender de matchmaking oficial.

Funciona com qualquer jogo que carregue `EOSSDK*.dll` (Palworld já validado; outros títulos UE com EOS devem funcionar direto).

## Início rápido

1. Instale **Python 3** e **LLVM/clang** (para compilar a proxy). Aponte o clang na GUI.
2. Baixe uma `steam_api64.dll` do **Goldberg Emulator** (Windows x64) e guarde em algum lugar — vai ser reusada em todos os jogos.
3. Baixe **Steamless.CLI.exe** (https://github.com/atom0s/Steamless) — necessário para jogos com stub DRM Steam. Aponte na GUI ou use `Auto`.
4. Execute `Launch.bat`.
5. Aponte a pasta do jogo → **Analisar** → **Aplicar setup** → **Jogar**.

## O que o EOSLANKit faz

| Ação | Efeito |
|------|--------|
| **Steamless** | Detecta stub Steam DRM (`.bind`/`SteamStub`) no EXE e invoca `Steamless.CLI.exe` para unpack. Backup `*.exe.steamdrm.bak`. Skip se não wrapped |
| **Goldberg** | Copia `steam_api64.dll` para raiz + todo `Engine/Binaries/ThirdParty/Steamworks/Steamv*/Win64/` + `Binaries/Win64/` |
| **steam_settings** | Escreve `configs.user.ini/main.ini/app.ini/custom_broadcasts.txt/steam_appid.txt` em todos os locais que o Goldberg lê |
| **Proxy EOS** | Compila DLL zero-CRT (~55 KB) com 10 hooks + forward do resto pra `EOSSDK_orig.dll` |
| **Patch EXE** | Delay-load MSVC ou offsets pré-mapeados em `known_offsets.json` (indexado por sha256) |
| **Launcher** | Gera `Play-<Game>.bat` que roda o Shipping direto e fecha popup residual do EOS via `PostMessage Enter` |
| **Verify** | Health-check pós-instalação (proxy, backups, INIs, DLLs Goldberg) |
| **Perfis** | `config/profiles/<hash>.json` — reaplica/restaura tudo de qualquer jogo já configurado |

## Estrutura do kit

```
EOSLANKit/
├── Launch.bat              # Abre a GUI
├── gui/launcher.py         # Interface tkinter
├── src/                    # Código C da proxy EOS
├── tools/                  # Scripts Python
│   ├── detect.py           # Detecta EOSSDK + Shipping + Steamworks
│   ├── steamless.py        # Detecta e remove stub Steam DRM via Steamless.CLI
│   ├── goldberg.py         # Instala steam_api64.dll Goldberg
│   ├── steam_settings.py   # Escreve configs Goldberg
│   ├── gen_def.py          # .def com forwards
│   ├── exe_patcher.py      # Patch (delay-load ou known_offsets)
│   ├── install_proxy.py    # Instala proxy + backup
│   ├── launcher_gen.py     # Gera Play-<Game>.bat/.ps1
│   ├── profile.py          # Perfil por jogo
│   ├── verify.py           # Health-check pos-instalacao
│   ├── setup.py            # Orquestrador
│   ├── uninstall_proxy.py  # Restaura EOSSDK original
│   └── restore_exe.py      # Restaura EXE original
├── build/                  # build.ps1 / proxy compilada
└── config/
    ├── intercepted.json    # Exports hook + globs de descoberta
    ├── defaults.json       # SteamID/nick/broadcast + goldberg_source
    ├── known_offsets.json  # Offsets EXE por sha256
    └── profiles/           # Perfis por jogo (gerado)
```

## Restaurar tudo

- **EOSSDK:** botão *Restaurar EOSSDK* na GUI (ou `tools/uninstall_proxy.py`).
- **EXE:** botão *Restaurar EXE* (usa `.eoslankit.bak`) ou `tools/restore_exe.py`.

## Requisitos

- Windows 10/11 x64
- Python 3.x
- LLVM/clang 64-bit (`clang`, `lld-link`)
- Windows SDK (`kernel32.lib`)
- Uma `steam_api64.dll` do Goldberg (obtenha manualmente uma vez)
- `Steamless.CLI.exe` (para jogos com stub Steam DRM)

## Gerar `EOSLANKit.exe`

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File build-exe.ps1
```

Requer Python 3. O script instala PyInstaller e produz `dist/EOSLANKit/EOSLANKit.exe` + pasta `_internal/`. Distribua a pasta `dist/EOSLANKit/` inteira. Na primeira execução, o `.exe` extrai `config/`, `build/` e `src/` para o próprio diretório (assim `defaults.json`, `profiles/` e `known_offsets.json` ficam editáveis).

O `Launch.bat` detecta automaticamente `dist/EOSLANKit/EOSLANKit.exe` e prefere ele sobre o modo Python.

## Créditos

**Made By: n3sec** — [n3sec.com](https://n3sec.com)
