# 反转家教 Android APK 打包

把 `../static/app/` 的 PWA 用 Capacitor 包成 .apk。**纯本地、无网也能跑**（mock 模式）。

## 前置环境（一次性）

- Node 18+ ✅
- JDK 17（`winget install Microsoft.OpenJDK.17`）
- Android SDK（platform-android-34 + build-tools-34.0.0 + platform-tools）

## 出包步骤

```powershell
# 1. 装 npm 依赖（约 30s）
npm install

# 2. 复制 web 资产 + 生成 android 工程
node sync-web.js
npx cap add android       # 仅首次
npx cap sync android      # 后续每次改 web 都跑这个

# 3. 编译 APK
cd android
.\gradlew assembleDebug   # 首次 ~10min（下 gradle + 依赖）
# 产出：android/app/build/outputs/apk/debug/app-debug.apk

# 4. 装机
adb install -r app/build/outputs/apk/debug/app-debug.apk
# 或者把 .apk 用 U 盘/微信 传到手机点击安装（需开「未知来源」）
```

## 改了 web 资产怎么办

```powershell
npm run sync   # = sync-web.js + cap sync android
# 然后重新 gradlew assembleDebug
```

## 签名发布版（可选，自用免）

debug APK 默认有 Android debug 签名，可直接装。如需 Play Store 发布，参考
Capacitor 官方文档生成 keystore。

## 应用内检查更新

移动端设置页里有「软件更新」：

1. 在 GitHub Releases 上传新版 APK。
2. 同时提供一个可公网访问的 `latest.json`，格式参考 `../static/app/latest.json`。
3. 默认 GitHub 更新源已经内置到应用中，用户无需手动填写。
4. 高级用户仍可在应用设置页改成自己的「更新源 URL」。
5. 以后应用可手动检查，或在启动时自动检查。

当前默认更新源：

```text
https://raw.githubusercontent.com/zhuxice-ctrl/Back_Teacher/main/static/app/latest.json
```

示例：

```json
{
  "versionCode": 2,
  "versionName": "0.12.0",
  "apkUrl": "https://github.com/<owner>/<repo>/releases/download/v0.12.0/app-release.apk",
  "publishedAt": "2026-05-14",
  "releaseNotes": [
    "新增检查更新功能",
    "优化移动端会话抽屉"
  ]
}
```

规则：`versionCode` 大于当前 APK 的 `versionCode` 才提示更新；如果没有 `versionCode`，则比较 `versionName`。
