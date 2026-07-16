# EOSLANKit

EOSLANKit helps you play Unreal Engine games that use Steam and Epic Online Services (EOS) with friends over LAN or offline, without official Steam/Epic matchmaking.

It is meant for your own game copies and your own dedicated server (for example over Hamachi or Radmin). It is not a crack for official online servers.

The tool walks you through Steam DRM unpack (Steamless), Steam API emulation (Goldberg), an EOS SDK proxy DLL, optional EXE patches, and a simple launcher. It works with games that ship EOSSDK*.dll. Palworld was tested; other UE + EOS titles should work the same way.

How to use it

Install Python 3 and LLVM/clang (needed to build the EOS proxy). Download a Goldberg steam_api64.dll (Windows x64) and Steamless.CLI.exe from https://github.com/atom0s/Steamless. Run Launch.bat, point it at your game folder, click Analyze, then Apply setup, then Play. You can set SteamID, nickname, and paths for Goldberg and Steamless in the GUI.

What it does

Steamless unpacks Steam DRM stubs on the game EXE when needed. Goldberg replaces steam_api64.dll and writes steam_settings so the game thinks Steam is present. The EOS proxy replaces EOSSDK-Win64-Shipping.dll, keeps a backup as EOSSDK_orig.dll, and reports a logged-in EOS session so multiplayer UI stays enabled. Optional EXE patching covers delay-load EOS stubs. A Play-Game.bat launcher starts the shipping EXE and dismisses leftover EOS popups. Profiles remember each game so you can reapply or restore later.

Requirements

Windows 10/11 x64, Python 3, LLVM/clang with Windows SDK (kernel32.lib), Goldberg steam_api64.dll, and Steamless.CLI.exe when the EXE is Steam-wrapped.

Build a standalone EXE

Run: powershell -NoProfile -ExecutionPolicy Bypass -File build-exe.ps1

That uses PyInstaller and creates dist/EOSLANKit/. Launch.bat prefers that EXE when it exists.

Restore

Use Restore EOSSDK or Restore EXE in the GUI, or the matching scripts under tools/.

Made by n3sec — https://n3sec.com
