// 把 ../static/app/ 同步到 ./www/（Capacitor 打包源目录）
const fs = require('fs');
const path = require('path');

const SRC = path.resolve(__dirname, '..', 'static', 'app');
const DST = path.resolve(__dirname, 'www');

function rmrf(p) {
  if (!fs.existsSync(p)) return;
  for (const f of fs.readdirSync(p)) {
    const fp = path.join(p, f);
    if (fs.statSync(fp).isDirectory()) rmrf(fp);
    else fs.unlinkSync(fp);
  }
  fs.rmdirSync(p);
}
function cprf(src, dst) {
  fs.mkdirSync(dst, { recursive: true });
  for (const f of fs.readdirSync(src)) {
    const sp = path.join(src, f);
    const dp = path.join(dst, f);
    if (fs.statSync(sp).isDirectory()) cprf(sp, dp);
    else fs.copyFileSync(sp, dp);
  }
}

rmrf(DST);
cprf(SRC, DST);
console.log(`[sync-web] ${SRC} -> ${DST} ok`);
