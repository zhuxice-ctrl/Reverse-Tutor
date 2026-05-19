# Reverse Tutor · Android APK 完整打包指南

> 本文档是 `mobile/` 工程当前**未完成**步骤的接力说明。
> 截至落笔时，**Capacitor 脚手架与 Android 工程已就绪**，缺的只是编译环境。

---

## ✅ 已经做完的（无需重做）

```
mobile/
├── package.json                   # @capacitor/cli + core + android v6
├── capacitor.config.json          # appId: com.reversetutor.app
├── sync-web.js                    # 把 ../static/app/ → mobile/www/
├── www/                           # ← PWA 静态资源 (sync-web.js 产物)
├── node_modules/                  # ← npm install 已装 (99 包)
└── android/                       # ← cap add android 已生成
    └── app/src/main/assets/public/  # ← cap sync android 已注入 web 资产
```

验证就绪：

```powershell
# 在 mobile/ 下
dir android\app\src\main\assets\public   # 应看到 index.html / manifest.json / sw.js 等
```

---

## ⏸ 剩余步骤（你来执行）

### Step 1：装 JDK 17

```powershell
winget install Microsoft.OpenJDK.17
# 装完**重开** PowerShell，验证：
java -version    # 应显示 openjdk version "17.x"
javac -version
```

如 winget 拉不动，备选：从 https://learn.microsoft.com/java/openjdk/download 手动下 17 MSI。

---

### Step 2：装 Android SDK（两选一）

#### 方式 A（推荐新手）：Android Studio

```powershell
winget install Google.AndroidStudio
```

- 装完启动 Android Studio → 首次启动会引导下载 **Android SDK Platform 34** + **Build-Tools 34.0.0** + **Platform-Tools**
- 默认 SDK 路径：`%LOCALAPPDATA%\Android\Sdk`，记下来

#### 方式 B（轻量无 IDE）：cmdline-tools 独立装

1. 下 cmdline-tools-win.zip：https://developer.android.com/studio#command-line-tools-only
2. 解压到 `D:\android-sdk\cmdline-tools\latest\`（**必须叫 `latest`**，否则 sdkmanager 跑不起）
3. PowerShell 跑：

```powershell
$env:ANDROID_HOME = "D:\android-sdk"
$env:Path += ";$env:ANDROID_HOME\cmdline-tools\latest\bin;$env:ANDROID_HOME\platform-tools"
sdkmanager --licenses           # 一路 y
sdkmanager "platforms;android-34" "build-tools;34.0.0" "platform-tools"
```

---

### Step 3：设环境变量（一次性、永久）

把以下设进 **系统环境变量**（控制面板 → 系统 → 高级 → 环境变量），或临时用 PowerShell：

```powershell
# 临时（当前会话）
$env:JAVA_HOME = "C:\Program Files\Microsoft\jdk-17.x.x-hotspot"   # ← 改成实际路径
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"                # Studio 默认
$env:Path += ";$env:JAVA_HOME\bin;$env:ANDROID_HOME\platform-tools"

# 永久（推荐 setx；要重开终端才生效）
setx JAVA_HOME "C:\Program Files\Microsoft\jdk-17.x.x-hotspot"
setx ANDROID_HOME "$env:LOCALAPPDATA\Android\Sdk"
```

验证：

```powershell
java -version
echo $env:ANDROID_HOME
dir $env:ANDROID_HOME\platforms       # 应有 android-34
```

---

### Step 4：编译 APK

```powershell
cd F:\xw\reverse-tutor\mobile\android
.\gradlew assembleRelease
```

**首次跑会发生什么**：

| 阶段 | 时长 | 下载量 |
|---|---|---|
| 下 Gradle 8.x 本体 | 2-5 min | ~150 MB |
| 下 AGP + Capacitor 依赖 | 3-8 min | ~300 MB |
| Kotlin compile + 资源打包 + dex | 1-3 min | - |
| **总计** | **~10-15 min** | **~450 MB** |

国内 Gradle / Maven Central 可能慢。备选：在 `android/build.gradle` 顶部、`settings.gradle` 里加阿里云镜像（必要再说）。

**产出**：

```
mobile/android/app/build/outputs/apk/release/app-release.apk
```

发布时复制并重命名为：

```
Reverse-Tutor-v{versionName}.apk
```

例如：

```
Reverse-Tutor-v0.17.0.apk
```

正式发布文件名不要带 `test` 或 `debug` 后缀。

---

### Step 5：装到手机

#### 方式 A：USB + adb

```powershell
# 手机开发者模式 + USB 调试已开
adb devices                                  # 看到设备
adb install -r app/build/outputs/apk/release/app-release.apk
```

#### 方式 B：传 APK 文件

把 `Reverse-Tutor-v{versionName}.apk` 通过微信/QQ/U 盘传到手机 → 点击安装（需要**允许未知来源**）。

---

## 🔁 后续改了 web 端怎么重出 APK

```powershell
cd F:\xw\reverse-tutor\mobile
node sync-web.js              # ../static/app/ → www/
.\node_modules\.bin\cap sync android   # www/ → android/.../assets/public/
cd android
.\gradlew assembleRelease
```

或者 `npm run build:apk` 一条命令搞定（已在 `package.json` 里配好）。

---

## 🚨 常见坑

| 报错 | 原因 | 解法 |
|---|---|---|
| `SDK location not found` | 没设 `ANDROID_HOME` | 见 Step 3，并在 `android/local.properties` 加 `sdk.dir=...` |
| `Could not resolve com.android.tools.build:gradle` | 无法访问 dl.google.com | 全局开梯，或在 `android/build.gradle` 的 `repositories` 加阿里云：`maven { url 'https://maven.aliyun.com/repository/google' }` |
| `Unsupported class file major version` | JDK 版本不对（用了 8 或 21） | 必须 JDK 17 |
| `error: package android.support.v4...` | AGP 版本与 SDK 不匹配 | 升 `compileSdk` 到 34 |
| 装机时 "应用未安装" | 手机已装了同 appId 不同签名版本 | 如果旧版是 debug/test 包，需卸载后安装；以后正式包必须保持同一 release 签名 |

---

## 🔐 Android 签名规范（必须遵守）

从 `v0.17.0` 开始，Reverse Tutor 的正式 APK 必须固定使用当前 release 签名，不再生成新签名，也不再发布 debug 签名包。

当前固定签名配置：

| 项 | 值 |
|---|---|
| Keystore | `mobile/android/app/release.jks` |
| Alias | `reverse-tutor` |
| Android applicationId | `com.reversetutor.app` |
| APK 命名 | `Reverse-Tutor-v{versionName}.apk` |
| Android 桌面显示名 | 从 v0.17.1 起回归中文：`反转家教` |
| 证书 DN | `CN=Reverse Tutor, OU=App, O=ReverseTeacher, L=CN, ST=CN, C=CN` |
| 证书 SHA-256 | `d21ff63c6b75494dd2229caccd6977ec763c8b17d95807ff1d7c455d39ac41c2` |

硬性规则：

- 后续所有正式发布必须使用 `mobile/android/app/release.jks` 和 alias `reverse-tutor`。
- 不要删除、替换、重新生成 `release.jks`。
- 不要再用 Android Debug 签名发布对外 APK。
- 不要修改 `applicationId "com.reversetutor.app"`，否则旧用户无法覆盖升级。
- 从 v0.17.1 起手机桌面显示名回归 `反转家教`；仓库名、Release 标题、APK 文件名仍保持 `Reverse Tutor` / `Reverse-Tutor-v{versionName}.apk`。
- 如用户已安装旧 debug/test 包，第一次切到 `v0.17.0` release 签名时需要卸载旧包；从 `v0.17.0` 往后，只要保持该签名即可覆盖安装升级。

发布前必须校验签名：

```powershell
$apksigner = "$env:LOCALAPPDATA\Android\Sdk\build-tools\34.0.0\apksigner.bat"
& $apksigner verify --print-certs release-artifacts\Reverse-Tutor-v0.17.1.apk
```

输出中必须包含：

```text
Signer #1 certificate DN: CN=Reverse Tutor, OU=App, O=ReverseTeacher, L=CN, ST=CN, C=CN
Signer #1 certificate SHA-256 digest: d21ff63c6b75494dd2229caccd6977ec763c8b17d95807ff1d7c455d39ac41c2
```

---

## 🆘 卡住了找我

直接把报错粘给我，告诉我跑到哪一步。常见错都能 1-2 轮搞定。
