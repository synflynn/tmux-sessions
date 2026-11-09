#!/usr/bin/env python3
"""tmux-claude-sessions: keeps the Claude Code tmux sessions on this machine in line with claude_db.tmux_sessions.

The web page (web/index.html + api.php) only writes desired_state; this agent polls the table,
starts / stops the tmux sessions and writes actual_state, rss_mb and last_seen back. Nothing listens on this VM.
Once a minute it also writes the Claude Code version each session runs (claude_version) and the newest installed one
(host_stats.claude_latest); update_requested = 1 from the page restarts that session (--continue) on the newest.

At (service) start every session that is not running gets desired_state = start_on_boot, so after a reboot only
the boot sessions come up (the rest are started by hand from the page).
Sessions that are already running are left alone, so restarting this service never kills anything.
"""
import glob
import os
import re
import shlex
import socket
import subprocess
import sys
import time

import pymysql

DB_HOST = os.environ.get("TMUX_DB_HOST", "127.0.0.1")   # MariaDB/MySQL with claude_db (db/schema.sql)
DB_USER = os.environ.get("TMUX_DB_USER", "tmux_agent")
DB_NAME = os.environ.get("TMUX_DB_NAME", "claude_db")
DB_PASS_FILE = os.path.expanduser(os.environ.get("TMUX_DB_PASS_FILE", "~/.config/tmux-claude-sessions/db.pass"))   # never print it
CLAUDE = os.path.expanduser("~/.local/bin/claude")
POLL_S = 3
VERSION_EVERY_S = 60   # claude_version / claude_latest refresh (once a minute is enough)
STOP_WAIT_S = 15   # Claude gets SIGTERM first, the tmux session is killed after this
HOST = socket.gethostname()   # row in claude_db.host_stats (CPU / RAM gauge on the page)


def log(msg):
    print(msg, flush=True)


def db():
    with open(DB_PASS_FILE) as f:
        return pymysql.connect(host=DB_HOST, user=DB_USER, password=f.read().strip(), database=DB_NAME,
                               connect_timeout=5, autocommit=True, cursorclass=pymysql.cursors.DictCursor)


def tmux(*args):
    return subprocess.run(["tmux", *args], capture_output=True, text=True)


def running_sessions():
    r = tmux("list-sessions", "-F", "#{session_name}")
    return set(r.stdout.splitlines()) if r.returncode == 0 else set()


def tmux_name(alias):
    """tmux session names have no spaces: "my web server" -> "my-web-server" (the Remote Control name keeps the spaces).
    The Remote Control name (session_name) keeps its spaces."""
    return re.sub(r"\s+", "-", alias.strip())


def pane_pid(alias):
    r = tmux("list-panes", "-t", f"={alias}", "-F", "#{pane_pid}")
    return int(r.stdout.split()[0]) if r.returncode == 0 and r.stdout.strip() else None


def children():
    tree = {}
    for line in subprocess.run(["ps", "-eo", "pid=,ppid=,rss=,comm="], capture_output=True, text=True).stdout.splitlines():
        pid, ppid, rss, comm = line.split(None, 3)
        tree.setdefault(int(ppid), []).append((int(pid), int(rss), comm))
    return tree


def descendants(pid, tree):
    out = []
    for child in tree.get(pid, []):
        out.append(child)
        out.extend(descendants(child[0], tree))
    return out


def rss_mb(alias, tree):
    pid = pane_pid(alias)
    if pid is None:
        return None
    return sum(rss for _, rss, _ in descendants(pid, tree)) // 1024


_versions = {}   # tmux alias -> Claude Code version it runs
_latest = None
_versions_at = 0


def claude_version(alias, tree):
    pid = pane_pid(alias)
    for cpid, _, comm in descendants(pid, tree) if pid is not None else []:
        if comm == "claude":
            try:
                return os.path.basename(os.readlink(f"/proc/{cpid}/exe"))[:32]
            except OSError:
                return None
    return None


def refresh_versions(aliases, tree):
    global _latest, _versions_at
    _latest = os.path.basename(os.path.realpath(CLAUDE))[:32]
    _versions.clear()
    for alias in aliases:
        _versions[alias] = claude_version(alias, tree)
    _versions_at = time.time()


def start(row):
    alias, path, name = tmux_name(row["tmux_alias"]), row["project_path"], row["session_name"]
    if not os.path.isdir(path):
        return f"project path missing: {path}"
    # --continue fails with "No conversation found" in a folder that has never had a session
    transcripts = os.path.expanduser("~/.claude/projects/" + "".join(c if c.isalnum() else "-" for c in path))
    resume = "--continue " if glob.glob(os.path.join(transcripts, "*.jsonl")) else ""
    cmd = f"{shlex.quote(CLAUDE)} {resume}--remote-control {shlex.quote(name)}; exec bash -l"
    # Own transient scope: a tmux server started from here must not live in this service's cgroup,
    # or restarting the service would take every session down with it.
    r = subprocess.run(["systemd-run", "--user", "--scope", "--quiet", "--collect",
                        "tmux", "new-session", "-d", "-s", alias, "-c", path, f"bash -lc {shlex.quote(cmd)}"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return (r.stderr or r.stdout).strip()[:250] or f"tmux exit {r.returncode}"
    log(f"started {name} (tmux {alias}) in {path}")
    return None


def stop(row):
    alias = tmux_name(row["tmux_alias"])
    pid = pane_pid(alias)
    if pid is not None:
        for cpid, _, comm in descendants(pid, children()):
            if comm == "claude":
                try:
                    os.kill(cpid, 15)
                except ProcessLookupError:
                    pass
        deadline = time.time() + STOP_WAIT_S
        while time.time() < deadline and any(c == "claude" for _, _, c in descendants(pid, children())):
            time.sleep(0.5)
    tmux("kill-session", "-t", f"={alias}")
    log(f"stopped {row['session_name']} (tmux {alias})")


_last_cpu = None


def cpu_pct():
    global _last_cpu
    with open("/proc/stat") as f:
        vals = [int(v) for v in f.readline().split()[1:]]
    idle, total = vals[3] + vals[4], sum(vals[:8])   # idle + iowait; steal counts as busy
    pct = 0.0
    if _last_cpu and total > _last_cpu[1]:
        pct = 100.0 * (1 - (idle - _last_cpu[0]) / (total - _last_cpu[1]))
    _last_cpu = (idle, total)
    return round(pct, 1)


def report_host(conn):
    mem = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":")
            mem[k] = int(v.split()[0]) // 1024
    with conn.cursor() as cur:
        cur.execute("INSERT INTO host_stats (host, cpu_pct, mem_used_mb, mem_total_mb, swap_used_mb, claude_latest) "
                    "VALUES (%s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE cpu_pct=VALUES(cpu_pct), "
                    "mem_used_mb=VALUES(mem_used_mb), mem_total_mb=VALUES(mem_total_mb), swap_used_mb=VALUES(swap_used_mb), "
                    "claude_latest=VALUES(claude_latest)",
                    (HOST, cpu_pct(), mem["MemTotal"] - mem["MemAvailable"], mem["MemTotal"],
                     mem["SwapTotal"] - mem["SwapFree"], _latest))


def boot_reset(conn):
    up = running_sessions()
    with conn.cursor() as cur:
        cur.execute("SELECT id, tmux_alias, start_on_boot FROM tmux_sessions")
        for row in cur.fetchall():
            if tmux_name(row["tmux_alias"]) not in up:
                cur.execute("UPDATE tmux_sessions SET desired_state=%s WHERE id=%s",
                            ("running" if row["start_on_boot"] else "stopped", row["id"]))


def tick(conn):
    global _versions_at
    up = running_sessions()
    tree = children()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM tmux_sessions")
        rows = cur.fetchall()
    restarted = False
    for row in rows:
        alias, error = tmux_name(row["tmux_alias"]), None
        if row["update_requested"]:
            with conn.cursor() as cur:
                cur.execute("UPDATE tmux_sessions SET update_requested=0 WHERE id=%s", (row["id"],))
            if alias in up and row["desired_state"] == "running":
                with conn.cursor() as cur:
                    cur.execute("UPDATE tmux_sessions SET actual_state='starting' WHERE id=%s", (row["id"],))
                stop(row)
                error = start(row)
                restarted = True
                log(f"update: {row['session_name']} restarted on {os.path.basename(os.path.realpath(CLAUDE))}")
        elif row["desired_state"] == "running" and alias not in up:
            with conn.cursor() as cur:
                cur.execute("UPDATE tmux_sessions SET actual_state='starting' WHERE id=%s", (row["id"],))
            error = start(row)
            restarted = True
        elif row["desired_state"] == "stopped" and alias in up:
            with conn.cursor() as cur:
                cur.execute("UPDATE tmux_sessions SET actual_state='stopping' WHERE id=%s", (row["id"],))
            stop(row)
        is_up = alias in running_sessions()
        state = "error" if error else ("running" if is_up else "stopped")
        with conn.cursor() as cur:
            cur.execute("UPDATE tmux_sessions SET actual_state=%s, rss_mb=%s, claude_version=%s, last_seen=NOW(), "
                        "last_error=%s WHERE id=%s", (state, rss_mb(alias, tree) if is_up else None,
                                                      _versions.get(alias) if is_up else None, error, row["id"]))
    # a fresh claude needs a few seconds before /proc shows it; pick it up on one of the next ticks
    if restarted or time.time() - _versions_at >= VERSION_EVERY_S:
        refresh_versions(running_sessions(), children())
        if restarted:
            _versions_at = time.time() - VERSION_EVERY_S + 2 * POLL_S


def main():
    conn = None
    booted = False
    while True:
        try:
            if conn is None:
                conn = db()
            if not booted:
                boot_reset(conn)
                booted = True
                log("table read, boot sessions set")
            tick(conn)
            report_host(conn)
        except pymysql.MySQLError as e:
            log(f"db error: {e}")
            conn = None
        time.sleep(POLL_S)


if __name__ == "__main__":
    sys.exit(main())
