"""共享 fixtures：每个测试一个干净的临时 SQLite + 强制 mock LLM。

执行顺序要点：
  - 必须在 `import db` 之前设置 DB_URL 和清空 LLM_*，因为这两个模块在 import 时就读 env。
  - 通过 monkey-patch `llm._HAS_REAL=False` 保证即使用户机器有 .env 也不会触发真 LLM。
"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile

# 1. 在 import db / llm / engine 之前设置环境
_TMP_DIR = pathlib.Path(tempfile.mkdtemp(prefix="rt_test_"))
_DB_PATH = (_TMP_DIR / "test.db").as_posix()
os.environ["DB_URL"] = f"sqlite:///{_DB_PATH}"

# 强制 mock：保证测试不会真的去调外部 LLM
os.environ.pop("LLM_BASE_URL", None)
os.environ.pop("LLM_API_KEY", None)
os.environ.pop("LLM_MODEL", None)
os.environ.pop("LLM_API_TYPE", None)

# 让 tests/ 能 import 项目根目录的模块
_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

import pytest  # noqa: E402

import db  # noqa: E402
import llm  # noqa: E402
import engine  # noqa: E402

# 双保险：即使 dotenv 后续加载，也覆盖回 mock
llm._HAS_REAL = False
llm.LLM_BASE_URL = ""
llm.LLM_API_KEY = ""
llm.LLM_MODEL = ""
llm.LLM_API_TYPE = ""
llm.FREE_LLM_BASE_URL = ""
llm.FREE_LLM_API_KEY = ""
llm.FREE_LLM_MODEL = ""


@pytest.fixture(autouse=True)
def fresh_db():
    """每个测试前重置全部表 + 强制 LLM 回到 mock，保证用例间隔离。"""
    db.engine.dispose()      # 关掉所有连接，清掉 identity map
    db.Base.metadata.drop_all(db.engine)
    db.Base.metadata.create_all(db.engine)
    # seed 内置 persona 模板（生产是 startup 时，测试这里手动 seed）
    with db.SessionLocal() as s:
        db.seed_builtin_templates(s)
    # 测试中可能有用例调 apply_config 切到 live，结束后重置
    llm.apply_config("", "", "")
    llm.FREE_LLM_BASE_URL = ""
    llm.FREE_LLM_API_KEY = ""
    llm.FREE_LLM_MODEL = ""
    yield
    llm.apply_config("", "", "")
    llm.FREE_LLM_BASE_URL = ""
    llm.FREE_LLM_API_KEY = ""
    llm.FREE_LLM_MODEL = ""


@pytest.fixture
def db_sess():
    s = db.SessionLocal()
    try:
        yield s
    finally:
        s.close()
