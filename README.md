# EDispense PC-Side Services

**English** | [中文](#edispense-上位机服务)

Host-side services for the **EDispense** desktop solder-paste dispensing and PCB-design assistant. These run on a Windows PC and give the RK3588-based machine an offline AI assistant, offline speech-to-text, a single web entry point, and a remote motion-control bridge — all usable with **no internet connection** (the PC hosts its own Wi-Fi hotspot).

The companion on-device (RK3588) project lives in a separate repository.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Models](#models)
- [Configuration](#configuration)
- [Running](#running)
- [Security](#security)
- [License](#license)

## Features

- **Offline LLM** — Qwen2.5-3B (INT4) served through OpenVINO GenAI on the integrated GPU, exposed as an OpenAI-compatible API plus a built-in chat web page.
- **Offline ASR** — SenseVoice-Small (INT8) via sherpa-onnx, CPU-only, auto language detect (Chinese / English). Powers the voice button on the machine's touchscreen.
- **Reverse proxy** — one port-80 entry that routes `/ai`, `/gerber`, and `/control` to the right backend.
- **Remote motion control** — bridges browser requests to the board over an SSH tunnel.
- **Wi-Fi config agent** — lets the machine's touchscreen scan and join Wi-Fi networks.
- **mDNS** — advertises `edispense.local` so clients can reach the PC without typing an IP.

## Architecture

```
                 ┌───────────────────────────────────────────┐
 phone / board   │  PC (Windows)                              │
 browser ───────►│  :80  edispense_proxy.py                   │
   (hotspot)     │        ├─ /ai      → :8080 ov_llm_server    │
                 │        ├─ /gerber  → :8090 (board uploader) │
                 │        └─ /control → :8091 edispense_control│──SSH──► RK3588 board
                 │  :8010 asr_service.py  (voice → text)       │         (ui_cmd_bridge)
                 │  :8765 wifi_agent.py   (Wi-Fi scan/connect) │
                 │        edispense_mdns.py (edispense.local)  │
                 └───────────────────────────────────────────┘
```

| Service | File | Port | Notes |
|---|---|---|---|
| LLM | `server/ov_llm_server.py` | 8080 | OpenVINO GenAI, OpenAI-compatible `/v1/chat/completions` |
| ASR | `server/asr_service.py` | 8010 | sherpa-onnx SenseVoice, `POST /asr` |
| Proxy | `gateway/edispense_proxy.py` | 80 | prefix routing, SSE pass-through |
| Control | `gateway/edispense_control.py` | 8091 | HTTP → SSH tunnel → board |
| mDNS | `gateway/edispense_mdns.py` | — | advertises `edispense.local` |
| Wi-Fi agent | `wifi/wifi_agent.py` | 8765 | `netsh` wrapper for the touchscreen |

## Requirements

- Windows 10/11 (Mobile Hotspot / Wi-Fi Direct GO support for offline mode)
- Python 3.10+
- For the LLM: an Intel GPU (integrated is fine) with OpenVINO runtime
- `pip install -r requirements.txt`

## Models

Model weights are **not** included in this repo. Download them and place under `models/`:

- LLM: convert `Qwen/Qwen2.5-3B-Instruct` to INT4 OpenVINO IR → `models/qwen2.5-3b-int4-ov/`
- ASR: `FunAudioLLM/SenseVoiceSmall` INT8 ONNX → `models/sensevoice/` (`model.int8.onnx`, `tokens.txt`)

Paths are overridable via environment variables (see below).

## Configuration

All host-specific values (board address, credentials, hotspot SSID/password, model paths) are read from environment variables. Copy `.env.example` to `.env` and fill in your own values.

```
EDISPENSE_LLM_MODEL_DIR   path to the OpenVINO LLM IR directory
EDISPENSE_LLM_DEVICE      GPU | CPU | AUTO   (default GPU)
EDISPENSE_ASR_MODEL_DIR   path to the SenseVoice model directory
EDISPENSE_BOARD_HOST      RK3588 board IP for the SSH tunnel
EDISPENSE_BOARD_USER      board SSH user
EDISPENSE_BOARD_PWD       board SSH password
EDISPENSE_HOST_IP         IP to advertise over mDNS (empty = auto-detect)
EDISPENSE_WIFI_BIND_IP    bind IP for the Wi-Fi agent
EDISPENSE_AP_SSID         hotspot SSID
EDISPENSE_AP_PASS         hotspot passphrase
```

> Security note: `.env` is git-ignored. Never commit real credentials. The board SSH bridge uses password auth by default; prefer key-based auth on shared networks.

## Running

Start the services (each in its own terminal, or via the batch files in `scripts/`):

```bat
scripts\start_ov_server.bat     :: LLM  :8080
scripts\start_asr.bat           :: ASR  :8010
scripts\start_control.bat       :: control bridge :8091
python gateway\edispense_proxy.py    :: proxy :80  (run as admin for port 80)
python gateway\edispense_mdns.py     :: mDNS
python wifi\wifi_agent.py            :: Wi-Fi agent :8765
```

Offline hotspot (Windows Mobile Hotspot via WinRT):

```powershell
scripts\tether_start.ps1 -Ssid "EDispense-AP" -Passphrase "your-passphrase"
scripts\tether_info.ps1          # show current AP state
scripts\hotspot_restart.ps1      # restart tethering
```

Once the hotspot is up, a phone or the board can join it and open `http://edispense.local/` (or the PC's hotspot IP) to reach the AI assistant and control pages.

## Security

These services bind to the local network / hotspot and have **no authentication** by default. They are designed for an isolated, offline machine network. Do not expose them directly to the public internet. If you need remote access, put them behind a VPN or an authenticating reverse proxy.

## License

MIT — see [LICENSE](LICENSE). Third-party components and model licenses are listed in [NOTICE](NOTICE).

---

# EDispense 上位机服务

[English](#edispense-pc-side-services) | **中文**

**EDispense** 桌面级锡膏点胶与 PCB 设计助手的上位机（PC 端）服务。这些服务运行在 Windows PC 上，为基于 RK3588 的点锡机提供离线 AI 助手、离线语音转文字、统一 Web 入口以及远程运动控制桥接——全部可在**无互联网连接**的环境下使用（PC 自建 Wi-Fi 热点）。

配套的设备端（RK3588）项目位于独立仓库中。

## 目录

- [功能特性](#功能特性)
- [系统架构](#系统架构)
- [运行环境](#运行环境)
- [模型](#模型)
- [配置](#配置)
- [启动](#启动)
- [安全性](#安全性说明)
- [许可协议](#许可协议)

## 功能特性

- **离线大模型** — Qwen2.5-3B（INT4），通过 OpenVINO GenAI 在集成显卡上推理，对外提供 OpenAI 兼容 API 及内置聊天网页。
- **离线语音识别** — SenseVoice-Small（INT8），基于 sherpa-onnx，仅用 CPU，自动检测中英文语种。为点锡机触摸屏上的语音按钮提供支持。
- **反向代理** — 单一 80 端口入口，将 `/ai`、`/gerber`、`/control` 路由到对应后端。
- **远程运动控制** — 通过 SSH 隧道将浏览器请求桥接到点锡机。
- **Wi-Fi 配置代理** — 让点锡机触摸屏可扫描并连接 Wi-Fi 网络。
- **mDNS** — 广播 `edispense.local`，客户端无需输入 IP 即可访问 PC。

## 系统架构

```
                 ┌───────────────────────────────────────────┐
 手机 / 点锡机    │  PC (Windows)                              │
 浏览器  ───────►│  :80  edispense_proxy.py                   │
   (热点)        │        ├─ /ai      → :8080 ov_llm_server    │
                 │        ├─ /gerber  → :8090 (板端上传)       │
                 │        └─ /control → :8091 edispense_control│──SSH──► RK3588 点锡机
                 │  :8010 asr_service.py  (语音 → 文字)         │         (ui_cmd_bridge)
                 │  :8765 wifi_agent.py   (Wi-Fi 扫描/连接)     │
                 │        edispense_mdns.py (edispense.local)  │
                 └───────────────────────────────────────────┘
```

| 服务 | 文件 | 端口 | 说明 |
|---|---|---|---|
| 大模型 | `server/ov_llm_server.py` | 8080 | OpenVINO GenAI，OpenAI 兼容 `/v1/chat/completions` |
| 语音识别 | `server/asr_service.py` | 8010 | sherpa-onnx SenseVoice，`POST /asr` |
| 代理 | `gateway/edispense_proxy.py` | 80 | 前缀路由，SSE 透传 |
| 控制 | `gateway/edispense_control.py` | 8091 | HTTP → SSH 隧道 → 点锡机 |
| mDNS | `gateway/edispense_mdns.py` | — | 广播 `edispense.local` |
| Wi-Fi 代理 | `wifi/wifi_agent.py` | 8765 | 面向触摸屏的 `netsh` 封装 |

## 运行环境

- Windows 10/11（离线模式需支持移动热点 / Wi-Fi Direct GO）
- Python 3.10+
- 大模型需要：带 OpenVINO 运行时的 Intel 显卡（集成显卡即可）
- `pip install -r requirements.txt`

## 模型

模型权重**不包含**在本仓库中。请自行下载并放入 `models/` 目录：

- 大模型：将 `Qwen/Qwen2.5-3B-Instruct` 转换为 INT4 OpenVINO IR → `models/qwen2.5-3b-int4-ov/`
- 语音识别：`FunAudioLLM/SenseVoiceSmall` INT8 ONNX → `models/sensevoice/`（`model.int8.onnx`、`tokens.txt`）

模型路径可通过环境变量覆盖（见下文）。

## 配置

所有与主机相关的取值（点锡机地址、凭据、热点 SSID/密码、模型路径）均从环境变量读取。请将 `.env.example` 复制为 `.env` 并填入你自己的值。

```
EDISPENSE_LLM_MODEL_DIR   OpenVINO 大模型 IR 目录路径
EDISPENSE_LLM_DEVICE      GPU | CPU | AUTO   (默认 GPU)
EDISPENSE_ASR_MODEL_DIR   SenseVoice 模型目录路径
EDISPENSE_BOARD_HOST      SSH 隧道对应的 RK3588 点锡机 IP
EDISPENSE_BOARD_USER      点锡机 SSH 用户名
EDISPENSE_BOARD_PWD       点锡机 SSH 密码
EDISPENSE_HOST_IP         mDNS 广播的 IP（留空则自动探测）
EDISPENSE_WIFI_BIND_IP    Wi-Fi 代理绑定的 IP
EDISPENSE_AP_SSID         热点 SSID
EDISPENSE_AP_PASS         热点密码
```

> 安全提示：`.env` 已被 git 忽略。切勿提交真实凭据。点锡机 SSH 桥接默认使用密码认证；在共享网络上建议改用密钥认证。

## 启动

启动各服务（各自独立终端，或使用 `scripts/` 下的批处理文件）：

```bat
scripts\start_ov_server.bat     :: 大模型  :8080
scripts\start_asr.bat           :: 语音识别 :8010
scripts\start_control.bat       :: 控制桥接 :8091
python gateway\edispense_proxy.py    :: 代理 :80  (80 端口需管理员权限)
python gateway\edispense_mdns.py     :: mDNS
python wifi\wifi_agent.py            :: Wi-Fi 代理 :8765
```

离线热点（通过 WinRT 调用 Windows 移动热点）：

```powershell
scripts\tether_start.ps1 -Ssid "EDispense-AP" -Passphrase "your-passphrase"
scripts\tether_info.ps1          # 查看当前热点状态
scripts\hotspot_restart.ps1      # 重启热点
```

热点启动后，手机或点锡机即可接入并打开 `http://edispense.local/`（或 PC 的热点 IP）访问 AI 助手与控制页面。

## 安全性说明

这些服务绑定在本地网络 / 热点上，默认**无身份认证**。它们面向隔离的离线机器网络设计。请勿将其直接暴露到公网。若需要远程访问，请置于 VPN 或带认证的反向代理之后。

## 许可协议

MIT — 详见 [LICENSE](LICENSE)。第三方组件及模型许可协议列于 [NOTICE](NOTICE)。
