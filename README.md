# tmux sessions

A small web page that starts, stops and updates Claude Code sessions running in tmux on one Linux machine.
Every session runs as `claude [--continue] --remote-control <name>` in its own tmux session, so it can also be
used from the Claude app (Remote Control). Built for a home server; this repo is only the session management
part, no secrets and no host-specific data inside.

> **Installing on a server?** Clone this repo and tell Claude Code on that machine:
> *"read INSTALL.md and set this up here"*. [INSTALL.md](INSTALL.md) is written as step-by-step instructions
> for Claude (and for humans).

## What it does

- Table of sessions (name, project folder, tmux name, start on boot, state, Claude Code version, RAM).
- Start (play), stop (square) and update (refresh arrow) as icon buttons, no confirm dialogs.
- **update**: a running session keeps the Claude Code binary it was started with. The native installer updates
  `~/.local/bin/claude` on its own; the page shows each session's version (green = newest installed, yellow =
  older) and the update button restarts the session with `--continue` (same conversation) on the newest binary.
- Boot checkbox: after a reboot only the boot sessions come up.
- Drag handle to reorder rows (saved in the DB); CPU / RAM gauges of the machine.
- Works on phones (rows turn into cards under 720 px).

## How it works

```
browser -> web/index.html -> web/api.php -> MariaDB claude_db <- agent/tmux-claude-sessions.py (polls every 3 s)
```

- The page only writes wishes to the DB (`desired_state`, `start_on_boot`, `update_requested`, `sort_order`).
- The agent (systemd user service, on the machine where Claude runs) reads the table every 3 s, starts / stops the
  tmux sessions, writes `actual_state`, RAM, errors and the CPU/RAM gauge back, and once a minute the Claude
  version of every session plus the newest installed one. Nothing listens on the agent machine.
- Stop = SIGTERM to claude, wait 15 s, then `tmux kill-session`.
- Start uses `systemd-run --user --scope`, so restarting the agent service never kills running sessions
  (unit has `KillMode=process`).
- `--continue` is only used when the project folder already has a transcript (`~/.claude/projects/<path with ->`),
  otherwise claude would exit with "No conversation found".
- Sessions are added / removed by hand in the DB (`db/example-sessions.sql`); the page does not create rows.
- **One agent per database.** The agent manages *every* row of `tmux_sessions`, so two machines must not share
  one `claude_db`. Each machine gets its own DB (simplest: DB + web + agent all on that machine).

## Files

| File | What |
|---|---|
| `agent/tmux-claude-sessions.py` | the agent (Python 3, needs pymysql: `apt install python3-pymysql`) |
| `agent/tmux-claude-sessions.service` | systemd user unit (`~/.config/systemd/user/`) |
| `web/index.html` | the page (plain HTML + JS, no build step, no external files) |
| `web/api.php` | JSON API (PHP 8 + PDO MySQL) |
| `web/nginx-site.conf` | nginx site example (php-fpm) |
| `db/schema.sql` | tables `tmux_sessions` + `host_stats` |
| `db/users.sql` | DB users / grants template (`CHANGE_ME` passwords) |
| `db/example-sessions.sql` | example rows |

## Install

See [INSTALL.md](INSTALL.md) (Debian 13 tested).

## Config (agent, environment variables)

| Variable | Default |
|---|---|
| `TMUX_DB_HOST` | `127.0.0.1` |
| `TMUX_DB_USER` | `tmux_agent` |
| `TMUX_DB_NAME` | `claude_db` |
| `TMUX_DB_PASS_FILE` | `~/.config/tmux-claude-sessions/db.pass` |

The host name in the page title is the agent's hostname.

## Security notes

- Never commit passwords; both passwords live in files outside the repo.
- Writes need the header `X-Tmux-Web: 1` (blocks plain cross-site form posts), but there is **no authentication**:
  anyone who can open the page can start / stop sessions. Keep it LAN only, or put basic auth / a VPN in front.

## Ideas

- A config file instead of env vars, an install script, add/delete sessions from the page, optional login,
  a LICENSE file.
