#!/usr/bin/env python3
"""
dedup_catalog.py — data_source_catalog 去重脚本

同一 id 出现在多个 domain 或同 domain 内多次时, 保留一条:
  优先级: status available > degraded > unverified/unavailable/blocked
  同状态: evidence.sample 更长的优先 (信息更全)
  再同: 保留先出现的

用法:
  python3 dedup_catalog.py [catalog.json] [output.json]
  不传参: 原地去重 (先写 .dedup_tmp.json 验证后覆盖)
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))

STATUS_RANK = {
    "available": 3,
    "ok": 3,
    "degraded": 2,
    "unverified": 1,
    "unavailable": 0,
    "blocked": 0,
}


def _score(entry):
    ev = entry.get("evidence") or {}
    sample = ev.get("sample", "") if isinstance(ev, dict) else ""
    return (STATUS_RANK.get(entry.get("status", ""), 1), len(sample))


def dedup(catalog):
    seen = {}
    order = []
    dup_log = []
    domains = catalog.get("domains", {})
    for domain, items in domains.items():
        for item in items:
            rid = item.get("id")
            if rid is None:
                continue
            if rid in seen:
                kept_domain, kept = seen[rid]
                cand = (domain, item)
                if _score(item) > _score(kept):
                    kept_domain, kept = cand
                    seen[rid] = cand
                dup_log.append(f"{rid}: 保留 [{kept_domain}] 丢弃 [{domain}]")
            else:
                seen[rid] = (domain, item)
                order.append(rid)

    new_domains = {}
    for rid in order:
        domain, item = seen[rid]
        new_domains.setdefault(domain, []).append(item)
    return new_domains, dup_log


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else \
        "/root/workspace/stocks-data-live/data/research/data_source_catalog_20261013.json"
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(src), "dedup_catalog_v2.json")

    with open(src, encoding="utf-8") as f:
        catalog = json.load(f)
    total_before = sum(len(v) for v in catalog.get("domains", {}).values())

    new_domains, dup_log = dedup(catalog)
    total_after = sum(len(v) for v in new_domains.values())

    out = dict(catalog)
    out["domains"] = new_domains
    out["timestamp"] = datetime.now(CST).isoformat(timespec="seconds")
    out.setdefault("note", "")
    note = out["note"].rstrip()
    out["note"] = f"{note}\n去重: {total_before} -> {total_after} 条, 移除 {total_before - total_after} 条重复 (见 dup_log)".rstrip()
    out["dedup_log"] = dup_log
    out["dedup_at"] = out["timestamp"]

    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"条目: {total_before} -> {total_after} (移除 {total_before - total_after})")
    print(f"domain: {dict((k, len(v)) for k, v in new_domains.items())}")
    for line in dup_log:
        print("  ", line)
    print(f"→ {dst}")
    # 验证
    with open(dst, encoding="utf-8") as f:
        v = json.load(f)
    ids = [i.get("id") for d in v["domains"].values() for i in d]
    assert len(ids) == len(set(ids)), "去重后仍有重复 id!"
    print("验证: JSON 合法, id 无重复 ✓")


if __name__ == "__main__":
    main()
