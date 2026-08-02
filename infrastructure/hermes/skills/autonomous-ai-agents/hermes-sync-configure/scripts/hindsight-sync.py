#!/usr/bin/env python3
"""Hindsight Daily Sync — export all banks, reflect+retain, git push.

Canonical sync script for the hermes-sync-banks cron job (02:00 UTC daily).
Uses the local Hindsight REST API (Method D, preferred over MCP JSON-RPC).
Processes banks SEQUENTIALLY (reflect+retain are stateful).

Usage:
    HINDSIGHT_API=http://127.0.0.1:8888 python3 hindsight-sync.py

API base: reads HINDSIGHT_API env var, default http://127.0.0.1:8888.
If the mapped host port refuses connections while the container is healthy
(observed 2026-08-02: connection refused on 127.0.0.1:8888, container "Up
(healthy)"), get the container IP and point at it:
    docker inspect hindsight --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
    HINDSIGHT_API=http://<ip>:8888 python3 hindsight-sync.py

Run as a background process with notify_on_complete=true — full run of ~16
banks takes ~25-30 min (reflect budget=high is ~1.5-2.5 min per bank), which
exceeds foreground timeouts (300-420s kills mid-retain).
"""
import json, os, subprocess, time
from datetime import datetime, timezone
import urllib.request

API = os.environ.get("HINDSIGHT_API", "http://127.0.0.1:8888")
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
EXPORT = "/home/opc/workspace/toolset/infrastructure/hermes/banks"
SKIP = {"default", "test_one_bank.py", "sync_phase2_reflect.py", "sync_phase1_export.py",
        "sync_banks.py", "reflect-progress.json", "export-manifest-2026-07-22.json"}

def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)

def api_get(path, timeout=180):
    with urllib.request.urlopen(f"{API}{path}", timeout=timeout) as r:
        return json.loads(r.read().decode())

def api_post(path, body, timeout=300):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{API}{path}", data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def fetch_memories(bid):
    all_items, off = [], 0
    while True:
        r = api_get(f"/v1/default/banks/{bid}/memories/list?limit=500&offset={off}")
        items = r.get("items", [])
        all_items.extend(items)
        total = r.get("total", 0)
        if off + len(items) >= total:
            break
        off += 500
        if not items:
            break
    return all_items

def do_reflect(bid):
    q_full = ("Sintetiza las interacciones, decisiones, aprendizajes y cambios de las "
              "últimas 24 horas relacionados con este proyecto. ¿Qué se hizo? ¿Qué se "
              "aprendió? ¿Qué decisiones se tomaron?")
    q_short = "¿Qué cambios, entradas nuevas o decisiones de procesamiento hubo en las últimas 24 horas?"
    for q, budget, mt in ((q_full, "high", 4096), (q_short, "low", 1024)):
        try:
            r = api_post(f"/v1/default/banks/{bid}/reflect",
                         {"query": q, "budget": budget, "max_tokens": mt}, timeout=300)
            text = (r.get("text") or "").strip()
            if text:
                return text
        except Exception as e:
            log(f"  reflect attempt failed: {e}")
    return ""

def manual_summary(bid, mems):
    """Fallback: compose a summary from exported memories when reflect returns empty."""
    items = mems or []
    recents = [it for it in items if it.get("mentioned_at") or it.get("created_at")]
    recents.sort(key=lambda it: it.get("mentioned_at") or it.get("created_at") or "", reverse=True)
    sample = []
    for it in recents[:8]:
        t = (it.get("text") or it.get("content") or "").strip().replace("\n", " ")
        if t:
            sample.append(t[:160])
    ctxs = {}
    for it in items:
        c = it.get("context") or "general"
        ctxs[c] = ctxs.get(c, 0) + 1
    top_ctx = ", ".join(f"{k}={v}" for k, v in sorted(ctxs.items(), key=lambda x: -x[1])[:5])
    body = f"Resumen manual (reflect automático no disponible). {len(items)} memorias en total; contextos: {top_ctx}. "
    body += "Muestras recientes: " + (" || ".join(sample) if sample else "sin contenido textual disponible.")
    return body

def do_retain(bid, content, timeout=300):
    body = {"items": [{
        "content": content[:8000],
        "context": "daily-summary",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tags": ["daily-summary", TODAY, bid]}],
        "async": False}
    return api_post(f"/v1/default/banks/{bid}/memories", body, timeout=timeout)

# ---- Main ----
banks = api_get("/v1/default/banks").get("banks", [])
banks = [b for b in banks if b["bank_id"] not in SKIP]
banks.sort(key=lambda b: b["bank_id"])
log(f"Banks to process ({len(banks)}): {[b['bank_id'] for b in banks]}")

summary = {}
for b in banks:
    bid = b["bank_id"]
    t0 = time.time()
    log(f"=== {bid} (fact_count={b.get('fact_count')}) ===")
    try:
        os.makedirs(f"{EXPORT}/{bid}", exist_ok=True)
        mems = fetch_memories(bid)
        with open(f"{EXPORT}/{bid}/{TODAY}.json", "w") as f:
            json.dump({"export_date": TODAY, "bank_id": bid,
                       "total_memories": len(mems), "memories": mems},
                      f, indent=2, ensure_ascii=False, default=str)
        log(f"  exported {len(mems)} memories -> {EXPORT}/{bid}/{TODAY}.json")
    except Exception as e:
        log(f"  EXPORT FAILED: {e}")
        summary[bid] = "export_failed"
        continue

    text = do_reflect(bid)
    if not text:
        log("  reflect empty, building manual summary")
        text = manual_summary(bid, mems)
    try:
        do_retain(bid, text)
        log(f"  retained {len(text)} chars (tags daily-summary/{TODAY}/{bid})")
        summary[bid] = f"ok: {len(mems)} mems, retain {len(text)}ch"
    except Exception as e:
        # Timeout is transport-level; the retain often still lands server-side.
        log(f"  RETAIN FAILED (client timeout): {e}")
        log(f"  verify server-side: GET {API}/v1/default/banks/{bid}/memories/list?limit=3&tags=daily-summary and check mentioned_at")
        summary[bid] = f"retain_client_timeout (export ok: {len(mems)} mems — VERIFY server-side)"
    log(f"  done in {round(time.time()-t0)}s")

log("=== SYNC SUMMARY ===")
for k, v in summary.items():
    log(f"  {k}: {v}")

# ---- Git ----
repo = "/home/opc/workspace/toolset"
os.chdir(repo)

def git(cmd, timeout=180):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=repo)
    out = (r.stdout or "").strip().splitlines()
    err = (r.stderr or "").strip().splitlines()
    tail = " | ".join((out + err)[-3:])
    log(f"GIT {' '.join(cmd[:2])} rc={r.returncode}: {tail}")
    return r

# Clean possible stale rebase state
if os.path.isdir(".git/rebase-merge"):
    subprocess.run(["rm", "-fr", ".git/rebase-merge"])
    log("removed stale .git/rebase-merge")

git(["git", "pull", "--rebase", "origin", "main"])
git(["git", "add", "infrastructure/hermes/banks/"])
rc = git(["git", "commit", "-m", f"hermes-sync: banks {TODAY}"])
if rc.returncode == 0:
    git(["git", "push", "origin", "main"])
else:
    # nothing to commit or real error — check status
    st = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=repo).stdout
    if st.strip():
        log(f"commit failed but working tree not clean: {st[:400]}")
    else:
        log("nothing to commit (files unchanged) — no push needed")

log("SYNC COMPLETE")
