"""Токены, время и стоимость субагентов Claude Code по транскриптам, с дедупликацией по message.id.

Запуск: SUBAGENTS_DIR=~/.claude/projects/<проект>/<сессия>/subagents python usage_claude.py <agentId> ...
"""
import json, sys
from datetime import datetime
from pathlib import Path

import os
BASE = Path(os.environ['SUBAGENTS_DIR'])
# $ за 1M токенов: вход, выход; кеш: запись 5м = 1.25x, 1ч = 2x, чтение = 0.1x входа
PRICE = {'opus': (4.0, 20.0), 'sonnet': (2.0, 10.0), 'haiku': (1.0, 5.0)}
# доля цены входа при чтении кеша: Opus 5.5 = 0.05 ($0.20), остальные 0.1
READ_MULT = {'opus': 0.05, 'sonnet': 0.1, 'haiku': 0.1}

def family(model):
    for k in PRICE:
        if k in model:
            return k
    return None

def scan(path):
    msgs, tools, errors, stamps, model = {}, 0, 0, [], ''
    for line in path.open(encoding='utf-8'):
        rec = json.loads(line)
        ts = rec.get('timestamp')
        if ts:
            stamps.append(datetime.fromisoformat(ts.replace('Z', '+00:00')))
        m = rec.get('message') or {}
        if rec.get('type') == 'assistant' and m.get('usage'):
            model = m.get('model') or model
            msgs[m.get('id') or len(msgs)] = m['usage']
            for c in m.get('content') or []:
                if isinstance(c, dict) and c.get('type') == 'tool_use':
                    tools += 1
        if rec.get('type') == 'user':
            for c in m.get('content') or [] if isinstance(m.get('content'), list) else []:
                if isinstance(c, dict) and c.get('type') == 'tool_result' and c.get('is_error'):
                    errors += 1
    t = dict(inp=0, out=0, w5=0, w1=0, rd=0)
    ctx_max = 0
    for u in msgs.values():
        cc = u.get('cache_creation') or {}
        w1 = cc.get('ephemeral_1h_input_tokens', 0)
        w5 = cc.get('ephemeral_5m_input_tokens', u.get('cache_creation_input_tokens', 0) - w1)
        t['inp'] += u.get('input_tokens', 0); t['out'] += u.get('output_tokens', 0)
        t['w5'] += w5; t['w1'] += w1; t['rd'] += u.get('cache_read_input_tokens', 0)
        ctx_max = max(ctx_max, u.get('input_tokens', 0) + u.get('cache_creation_input_tokens', 0) + u.get('cache_read_input_tokens', 0))
    fam = family(model)
    pi, po = PRICE[fam]
    cost = {
        'input': t['inp'] * pi / 1e6, 'output': t['out'] * po / 1e6,
        'cache_write': (t['w5'] * 1.25 + t['w1'] * 2) * pi / 1e6, 'cache_read': t['rd'] * READ_MULT[fam] * pi / 1e6,
    }
    return dict(file=path.name, model=model, turns=len(msgs), tools=tools, tool_errors=errors,
                seconds=round((max(stamps) - min(stamps)).total_seconds()), **t,
                unique=t['inp'] + t['w5'] + t['w1'] + t['out'], billed_in_total=t['inp'] + t['w5'] + t['w1'] + t['rd'],
                ctx_max=ctx_max, cost={k: round(v, 3) for k, v in cost.items()}, cost_total=round(sum(cost.values()), 3))

ids = sys.argv[1:]
print(json.dumps([scan(BASE / f'agent-{i}.jsonl') for i in ids], ensure_ascii=False, indent=1))
