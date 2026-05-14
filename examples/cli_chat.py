"""命令行聊天客户端 —— 也是 Hermes / 任意 Agent 框架的集成示例。

用法：
  python examples/cli_chat.py
  python examples/cli_chat.py --server http://192.168.1.10:8765
  python examples/cli_chat.py --sid <existing_session_id>

Hermes / 其它 Agent 框架接入方式（核心三步）：
  POST {server}/api/sessions   一次性创建（auto_opening=true 会拿到第一句）
  POST {server}/api/sessions/{sid}/chat   每轮把用户输入打过来
  GET  {server}/api/sessions/{sid}        随时拉锚点/掌握度做监控
"""
from __future__ import annotations

import argparse
import sys

import httpx


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--server", default="http://127.0.0.1:8765")
    p.add_argument("--sid", default=None, help="复用已有会话 id；不传则创建新的")
    p.add_argument("--role", default="高三理科生")
    p.add_argument("--goal", default="数学一年内冲 130 分")
    args = p.parse_args()

    base = args.server.rstrip("/")
    with httpx.Client(timeout=60.0) as c:
        # 健康检查
        h = c.get(f"{base}/api/health").json()
        print(f"[server] mode={h['mode']} model={h.get('model') or 'mock'}\n")

        if args.sid:
            s = c.get(f"{base}/api/sessions/{args.sid}").json()
        else:
            s = c.post(f"{base}/api/sessions", json={
                "role": args.role,
                "goal": args.goal,
                "initial_requirements": [],
                "auto_opening": True,
            }).json()
            print(f"[new session] {s['id']}  {s['persona']['role']} · {s['persona']['goal']}")
        sid = s["id"]

        # 打印开场白（如果有）
        opening = next((m for m in s.get("messages", []) if m["role"] == "assistant"), None)
        if opening:
            print(f"\n🎓 学生 AI: {opening['content']}")

        # 主循环
        print("\n输入回复（:q 退出, :anchors 看锚, :insights 看进展, :export 导出 md）\n")
        while True:
            try:
                line = input("👤 你: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line == ":q":
                break
            if line == ":anchors":
                anchors = c.get(f"{base}/api/sessions/{sid}/anchors").json()
                for a in anchors:
                    print(f"  [{a['kind']:>11} w={a['weight']:.1f}] {a['content']}")
                continue
            if line == ":insights":
                full = c.get(f"{base}/api/sessions/{sid}").json()
                ai = [m for m in full["messages"] if m["role"] == "assistant"]
                m = full["mastery"]
                print(f"  轮数: {len(ai)} · 已追踪 {len(m)} 个知识点")
                for kp in sorted(m, key=lambda x: -x["level"])[:5]:
                    bar = "█" * int(kp["level"] * 10) + "░" * (10 - int(kp["level"] * 10))
                    print(f"  {bar} {kp['level']:.2f}  {kp['knowledge_point']}")
                continue
            if line == ":export":
                md = c.get(f"{base}/api/sessions/{sid}/export?format=md").text
                fn = f"session_{sid}.md"
                with open(fn, "w", encoding="utf-8") as fp:
                    fp.write(md)
                print(f"  导出到 {fn}")
                continue

            r = c.post(f"{base}/api/sessions/{sid}/chat", json={"message": line}).json()
            act = r.get("action", {})
            print(f"\n🎓 学生 AI [{act.get('type','?')}·kp={act.get('knowledge_point','?')}]:")
            print(f"  {r.get('reply','')}\n")


if __name__ == "__main__":
    sys.exit(main() or 0)
