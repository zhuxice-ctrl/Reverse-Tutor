<p align="center">
  <img src="static/app/icon-192.png" width="96" alt="Back Teacher logo">
</p>

<h1 align="center">反转家教 Back Teacher</h1>

<p align="center">
  把 AI 从“答案机器”变成会追问、会复盘、会持续推动目标的学生。
</p>

<p align="center">
  <a href="https://github.com/zhuxice-ctrl/Back_Teacher/releases/latest">
    <img alt="Release" src="https://img.shields.io/github/v/release/zhuxice-ctrl/Back_Teacher?style=for-the-badge&label=release&color=0f766e">
  </a>
  <img alt="Tests" src="https://img.shields.io/badge/tests-pytest-2563eb?style=for-the-badge">
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-334155?style=for-the-badge">
  <img alt="Android" src="https://img.shields.io/badge/android-capacitor-16a34a?style=for-the-badge">
</p>

<p align="center">
  <a href="https://dl.zeroxcore.tech/reverse-tutor/Back_Teacher-v0.16.0-debug.apk"><strong>下载 Android APK</strong></a>
  ·
  <a href="https://github.com/zhuxice-ctrl/Back_Teacher/releases/latest">查看最新版本</a>
  ·
  <a href="#快速开始">本地运行</a>
  ·
  <a href="#移动端打包">自己打包</a>
</p>

<p align="center">
  <img src="docs/assets/readme-showcase.svg" alt="Back Teacher showcase">
</p>

## 这是什么

反转家教是一个“反向教学”和“目标推动”工具。你不再只是向 AI 提问，而是让 AI 扮演学生、追问者、检查者或协作者。你需要把目标、知识或方案讲清楚，AI 会继续追问、复盘、记录锚点，并在后续对话中推动你把事情做完。

它最初适合学习场景：用“教别人”的方式逼自己真正理解。现在也支持更宽泛的目标型使用，例如项目推进、方案打磨、习惯监督、面试训练、产品讨论和个人任务复盘。

## 核心能力

| 能力 | 说明 |
|---|---|
| 反向教学对话 | AI 扮演你设定的人格，用追问和反馈逼近清晰表达，而不是直接替你完成。 |
| 目标锚点 | 记录目标、要求、知识点和新增约束，减少长对话中的跑偏。 |
| 洞察窗口 | 汇总掌握度、重点、下一步动作和对话中的结构化信息。 |
| 主动对话 | 在线模式下可按间隔主动发起提醒，离线模式保持静默，睡眠模式降低频率。 |
| 多模型接入 | 移动端支持 OpenAI Chat API 与 Anthropic Messages API 两类协议，内置 DeepSeek、OpenAI、Qwen、Kimi、Groq、OpenRouter、Ollama、LM Studio 等预设。 |
| 本地长期配置 | 移动端会把 LLM 配置和会话数据保存在设备侧，绑定 API 后可长期使用。 |
| Android 后台回复 | APK 内置后台服务，退出界面后仍可继续处理已提交的回复任务。 |
| 应用内更新 | 内置自建高速下载源和 GitHub 备用源，支持应用内检查新版 APK。 |

## 产品结构

<p align="center">
  <img src="docs/assets/readme-architecture.svg" alt="Back Teacher architecture">
</p>

```text
.
├── server.py                 # FastAPI 服务入口
├── engine.py                 # 反转家教核心对话引擎
├── llm.py                    # 服务端 LLM / mock 适配层
├── db.py                     # SQLite 数据模型与操作
├── adapters/                 # 飞书 / QQ / Hermes 等平台适配
├── static/index.html         # 桌面 Web UI
├── static/app/               # 移动端 PWA 源码
├── mobile/                   # Capacitor Android APK 工程
└── tests/                    # pytest 测试
```

## 快速开始

环境要求：

- Python 3.10+
- Node.js 18+，仅在打包移动端时需要
- Android Studio / Android SDK，仅在打包 APK 时需要

安装依赖并启动服务：

```powershell
pip install -r requirements.txt
copy .env.example .env
python -m uvicorn server:app --reload --host 127.0.0.1 --port 8000
```

打开：

- 桌面 Web：http://127.0.0.1:8000
- 移动 PWA：http://127.0.0.1:8000/app/

不配置 LLM 也能运行。项目会自动使用 mock 模式，适合本地演示、测试和开发。

## LLM 配置

服务端 `.env` 使用 OpenAI 兼容协议：

```env
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-your-key-here
LLM_MODEL=deepseek-v4-flash
```

移动端可以直接在应用内配置模型。当前移动端把“接口类型”明确分成两类：

| 接口类型 | 典型 URL | 适用模型 |
|---|---|---|
| OpenAI | `https://api.deepseek.com` | DeepSeek、OpenAI、Qwen、Kimi、Groq、OpenRouter、Ollama、LM Studio |
| Anthropic | `https://api.deepseek.com/anthropic` | 支持 Anthropic Messages API 的模型或兼容代理 |

如果模型不支持图片，发送图片或表情时不会让 DeepSeek 这类文本模型强行识图；多模态能力由你选择的模型预设决定。

## 移动端打包

```powershell
cd mobile
npm install
npm run build:apk
```

产物位置：

```text
mobile/android/app/build/outputs/apk/debug/app-debug.apk
```

当前公开测试包：

- 自建高速源：https://dl.zeroxcore.tech/reverse-tutor/Back_Teacher-v0.16.0-debug.apk
- GitHub Release：https://github.com/zhuxice-ctrl/Back_Teacher/releases/latest

## 应用更新

移动端默认使用自建更新源：

```text
https://dl.zeroxcore.tech/reverse-tutor/latest.json
```

更新规则：

- 优先比较 `versionCode`，新版必须大于当前 APK 的 `versionCode`。
- 如果没有 `versionCode`，再比较 `versionName`。
- 下载源优先使用自建源，失败后再尝试 GitHub Release 备用源。
- Android 侧不能静默安装 APK，下载完成后会打开系统安装器，由用户确认安装。

`latest.json` 示例：

```json
{
  "versionCode": 15,
  "versionName": "0.16.0",
  "apkUrl": "https://dl.zeroxcore.tech/reverse-tutor/Back_Teacher-v0.16.0-debug.apk",
  "apkMirrors": [
    "https://github.com/zhuxice-ctrl/Back_Teacher/releases/download/v0.16.0/Back_Teacher-v0.16.0-debug.apk"
  ],
  "publishedAt": "2026-05-16",
  "releaseNotes": [
    "重做接口类型配置",
    "替换启动封面并加入进入动画"
  ]
}
```

## 开发与测试

```powershell
pytest -q
```

移动端改动建议至少跑：

```powershell
pytest -q tests/test_mobile_persistence.py tests/test_android_background_llm.py tests/test_update_check_resilience.py
cd mobile
npm run build:apk
```

## API 简表

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| POST | `/api/sessions` | 创建会话 |
| GET | `/api/sessions` | 列出会话 |
| GET | `/api/sessions/{id}` | 获取会话详情 |
| DELETE | `/api/sessions/{id}` | 删除会话 |
| POST | `/api/sessions/{id}/chat` | 发送一轮对话 |
| POST | `/api/sessions/{id}/opening` | 触发开场 |
| GET / POST | `/api/sessions/{id}/anchors` | 查看或添加锚点 |
| GET | `/api/sessions/{id}/export` | 导出会话 |
| POST | `/api/adapters/{platform}/webhook` | 平台 webhook |
| GET | `/api/bindings` | 查看平台绑定 |

## 当前状态

这个项目还处在快速迭代阶段，Debug APK 适合自用测试。正式分发仍需要 release 签名、权限说明、隐私政策和更完整的设备兼容测试。

## 加入交流群

欢迎入qq群反馈给我更新动力。

<p align="center">
  <img src="docs/assets/qq-group.jpg" width="320" alt="反转家教 QQ 群二维码">
</p>

<p align="center">
  QQ 群：<strong>897804938</strong>
</p>
