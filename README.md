# Back_Teacher / 反转家教

反转家教，让教学成为你最好的学习方式。

这是一个“反向家教”学习工具：AI 扮演学生，用户扮演老师。用户需要把知识讲清楚，AI 会根据回答质量继续追问、换题、鼓励或推进，从而让用户在“教别人”的过程中加深理解。

## 核心功能

- **反向教学对话**：AI 扮演你设定的学生角色，主动请教你。
- **结构化评估**：每轮对话都会评估正确度、深度、情绪和下一步动作。
- **锚点防漂移**：用户目标、学习重点和新增诉求会写入 anchor，后续对话不会跑偏。
- **掌握度追踪**：按知识点维护 mastery，动态调整难度。
- **Mock 模式**：没有配置 LLM API 也能本地体验。
- **OpenAI 兼容接口**：支持 DeepSeek、Qwen、Moonshot、自部署 vLLM、Ollama 等兼容接口。
- **Web + 移动端**：提供桌面 Web UI、移动 PWA，并可用 Capacitor 打包 APK。
- **本地数据**：服务端使用 SQLite，移动 PWA 使用 IndexedDB。
- **检查更新**：移动端内置 GitHub `latest.json` 更新源，手动或启动时检查新版 APK。

## 项目结构

```text
.
├─ server.py                 # FastAPI 服务入口
├─ engine.py                 # 反转家教核心对话引擎
├─ llm.py                    # LLM / mock 模式封装
├─ db.py                     # SQLite 数据模型与操作
├─ adapters/                 # 飞书 / QQ / Hermes 等平台适配
├─ static/index.html         # 桌面 Web UI
├─ static/app/               # 移动 PWA 源码
├─ mobile/                   # Capacitor Android APK 工程
├─ tests/                    # pytest 测试
└─ examples/cli_chat.py      # CLI 对话示例
```

## 快速启动

环境要求：

- Python 3.10+
- Node.js 18+（仅打包移动端时需要）
- Android Studio / Android SDK（仅打包 APK 时需要）

安装 Python 依赖：

```powershell
pip install -r requirements.txt
copy .env.example .env
```

启动服务：

```powershell
python -m uvicorn server:app --reload --host 127.0.0.1 --port 8000
```

打开：

- 桌面 Web：<http://127.0.0.1:8000>
- 移动 PWA：<http://127.0.0.1:8000/app/>

## LLM 配置

如果不配置 LLM，应用会自动使用 mock 模式，适合调试和演示。

如需接入真实模型，在 `.env` 或 Web 设置中配置：

```env
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-your-key-here
LLM_MODEL=deepseek-chat
```

也可以在运行中的 Web UI 里打开 LLM 设置，直接保存配置。

## APK 打包

移动端工程位于 `mobile/`。

常用命令：

```powershell
cd mobile
npm install
npm run sync
cd android
.\gradlew.bat assembleDebug
```

产物：

```text
mobile/android/app/build/outputs/apk/debug/app-debug.apk
```

当前项目已经配置过 Android SDK 和 Gradle wrapper。若换电脑，需要参考 [mobile/BUILD_APK.md](mobile/BUILD_APK.md) 重新配置 JDK / Android SDK。

## 检查更新

移动端设置页有「软件更新」：

1. 在 GitHub Releases 上传新版 APK。
2. 提供一个公网可访问的 `latest.json`。
3. 默认更新源已经内置到应用中，用户无需手动填写。
4. 高级用户仍可在应用设置页改成自己的 `latest.json` 地址。
5. 应用可手动检查，也可启动时自动检查。

`latest.json` 示例：

```json
{
  "versionCode": 2,
  "versionName": "0.12.0",
  "apkUrl": "https://github.com/zhuxice-ctrl/Back_Teacher/releases/download/v0.12.0/app-release.apk",
  "publishedAt": "2026-05-14",
  "releaseNotes": [
    "新增检查更新功能",
    "优化移动端会话抽屉"
  ]
}
```

规则：

- 优先比较 `versionCode`，新版必须大于当前 APK 的 `versionCode`。
- 如果没有 `versionCode`，再比较 `versionName`。
- 安卓侧载 APK 不能静默自动安装，只能提示用户下载并手动安装。

模板文件在 [static/app/latest.json](static/app/latest.json)。

当前默认更新源：

```text
https://raw.githubusercontent.com/zhuxice-ctrl/Back_Teacher/main/static/app/latest.json
```

## 版本更新管理

建议使用语义化版本：

- `0.11.0`：功能版本
- `0.11.1`：修复版本
- `0.12.0`：新增功能
- `1.0.0`：稳定发布

每次发布新版建议按这个顺序：

```powershell
# 1. 修改版本号
# mobile/package.json: version
# mobile/android/app/build.gradle: versionCode + versionName
# static/app/index.html: APP_VERSION_CODE + APP_VERSION_NAME
# static/app/latest.json: versionCode + versionName + apkUrl + releaseNotes

# 2. 跑测试
pytest

# 3. 同步并打 APK
cd mobile
npm run sync
cd android
.\gradlew.bat assembleDebug

# 4. 提交
git status
git add .
git commit -m "release: v0.12.0"
git tag v0.12.0
git push
git push origin v0.12.0
```

然后到 GitHub Releases：

1. 选择 tag，例如 `v0.12.0`。
2. 上传 APK。
3. 写更新说明。
4. 更新 `latest.json` 的 `apkUrl`。

## 测试

```powershell
pytest
```

当前测试覆盖：

- 核心对话引擎
- LLM mock / live 配置
- 数据库 CRUD
- 平台 onboarding
- FastAPI 接口
- persona 模板

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
| GET / POST | `/api/sessions/{id}/anchors` | 查看 / 添加锚点 |
| GET | `/api/sessions/{id}/export` | 导出会话 |
| POST | `/api/adapters/{platform}/webhook` | 平台 webhook |
| GET | `/api/bindings` | 查看平台绑定 |

## 当前限制

- 飞书 / QQ 回推目前是适配层 stub，生产使用前要补签名校验和真实发送 worker。
- 移动端直连云端 LLM API 可能遇到 CORS 限制，本地 Ollama 或自部署 API 更适合 PWA。
- Debug APK 适合自用测试；正式分发需要 release 签名。
