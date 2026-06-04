# Reverse Tutor Android APK 打包

把 `../static/app/` 的 PWA 用 Capacitor 包成 .apk。未配置 API 时优先走内置免费 GLM 直连接口，离线或接口失败时仍可回退到本地 mock。

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
.\gradlew assembleRelease # 首次 ~10min（下 gradle + 依赖）
# 产出：android/app/build/outputs/apk/release/app-release.apk

# 4. 装机
adb install -r app/build/outputs/apk/release/app-release.apk
# 或者把 .apk 用 U 盘/微信 传到手机点击安装（需开「未知来源」）
```

## 改了 web 资产怎么办

```powershell
npm run sync   # = sync-web.js + cap sync android
# 然后重新 gradlew assembleRelease
```

## 签名发布版（可选，自用免）

当前工程已配置 release 签名，正式测试包使用 release APK；如需 Play Store 发布，参考
Capacitor 官方文档管理 keystore。

签名规范固定如下，后续发布不要再变动：

- Keystore：`mobile/android/app/release.jks`
- Alias：`reverse-tutor`
- Android applicationId：`com.reversetutor.app`
- 证书 DN：`CN=Reverse Tutor, OU=App, O=ReverseTeacher, L=CN, ST=CN, C=CN`
- 证书 SHA-256：`d21ff63c6b75494dd2229caccd6977ec763c8b17d95807ff1d7c455d39ac41c2`
- 正式 APK 命名：`Reverse-Tutor-v{versionName}.apk`
- Android 桌面显示名：从 v0.17.1 起回归中文 `反转家教`

不要删除、替换或重新生成 `release.jks`；不要再用 Android Debug 签名发布对外 APK。旧 debug/test 包切到 v0.17.0 release 签名时需要卸载旧包，后续只要保持该签名即可覆盖升级。Android 桌面显示名从 v0.17.1 起回归 `反转家教`，仓库名、Release 标题和 APK 文件名仍保持 Reverse Tutor / `Reverse-Tutor-v{versionName}.apk`。

## 应用内检查更新

移动端设置页里有「软件更新」：

1. 在 GitHub Releases 上传新版 APK。
2. 同时提供一个可公网访问的 `latest.json`，格式参考 `../static/app/latest.json`。
3. 默认 GitHub 更新源已经内置到应用中，用户无需手动填写。
4. 高级用户仍可在应用设置页改成自己的「更新源 URL」。
5. 以后应用可手动检查，或在启动时自动检查。

当前默认更新源：

```text
https://dl.zeroxcore.tech/reverse-tutor/latest.json
```

示例：

```json
{
  "versionCode": 42,
  "versionName": "0.19.3",
  "apkUrl": "https://dl.zeroxcore.tech/reverse-tutor/Reverse-Tutor-v0.19.3.apk",
  "apkMirrors": [
    "https://github.com/zhuxice-ctrl/Reverse-Tutor/releases/download/v0.19.3/Reverse-Tutor-v0.19.3.apk"
  ],
  "publishedAt": "2026-06-05",
  "releaseNotes": [
    "修复真机长按会话后操作菜单仍可能跑到屏幕外的问题",
    "修复升级后 WebView 可能继续读取旧 app shell 缓存的问题",
    "移除轻聊天回复被过度压短的硬限制"
  ]
}
```

规则：`versionCode` 大于当前 APK 的 `versionCode` 才提示更新；如果没有 `versionCode`，则比较 `versionName`。
