from __future__ import annotations

import argparse
import secrets
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import db
import trial


ALPHABET = "".join(ch for ch in string.ascii_uppercase + string.digits if ch not in "O0I1")


def make_code(prefix: str, length: int) -> str:
    body = "".join(secrets.choice(ALPHABET) for _ in range(length))
    return f"{prefix}-{body}" if prefix else body


def yuan_to_micro(value: float) -> int:
    return int(round(float(value) * 1_000_000))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Reverse Tutor trial redemption codes.")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--prefix", default="RT")
    parser.add_argument("--length", type=int, default=10)
    parser.add_argument("--total-yuan", type=float, default=0.5)
    parser.add_argument("--daily-yuan", type=float, default=0.0, help="0 means no daily cap")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    db.init_db()
    created: list[str] = []
    with db.SessionLocal() as s:
        while len(created) < args.count:
            code = trial.normalize_code(make_code(args.prefix, args.length))
            if s.get(db.TrialCode, code):
                continue
            s.add(db.TrialCode(
                code=code,
                total_quota_micro_cny=yuan_to_micro(args.total_yuan),
                daily_quota_micro_cny=yuan_to_micro(args.daily_yuan),
                note=args.note,
            ))
            created.append(code)
        s.commit()

    for code in created:
        print(code)


if __name__ == "__main__":
    main()
