"""Токены, время и вызовы по журналу сеанса Codex (rollout-*.jsonl).

Запуск: python codex_usage.py <rollout.jsonl> [...]
"""
import json
import sys
from datetime import datetime


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


for path in sys.argv[1:]:
    first = last = None
    model = effort = None
    total = None
    tools = mcp = 0
    rate = None
    for line in open(path, encoding="utf-8"):
        o = json.loads(line)
        p = o.get("payload", {}) or {}
        t = p.get("type")
        if o.get("type") == "turn_context":
            model = p.get("model", model)
            effort = p.get("effort", effort) or p.get("reasoning_effort", effort)
        if t in ("function_call", "custom_tool_call"):
            tools += 1
            if (p.get("name") or "").startswith("mcp__") or "tc_" in (p.get("name") or ""):
                mcp += 1
            stamp = ts(o["timestamp"])
            first = first or stamp
            last = stamp
        if t == "token_count" and p.get("info"):
            total = p["info"].get("total_token_usage")
            rate = p.get("rate_limits")
        if t in ("agent_message",) and first:
            last = ts(o["timestamp"])
    print(path.rsplit("/", 1)[-1])
    print(f"  модель {model}, effort {effort}")
    if first:
        print(f"  время {(last - first).total_seconds() / 60:.1f} мин (первый вызов -> последнее сообщение)")
    print(f"  вызовов инструментов {tools}")
    print(f"  токены {json.dumps(total, ensure_ascii=False)}")
    print(f"  лимиты {json.dumps(rate, ensure_ascii=False)}")
