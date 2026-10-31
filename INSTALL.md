# Installing tmux sessions on a machine

Written for Claude Code running on the target machine (a human can follow it the same way).
Goal: on **this** machine, set up the DB, the web page and the agent, all local (the "all-in-one" layout).
Tested on Debian 13. Work through the steps in order and check each one before moving on.

## Rules for Claude

- **Ask the user before you start** (in one message):
  1. Which Linux user runs the Claude sessions (default: the current user, not root)?
  2. Which sessions to create: for each one a name, a project folder and whether it starts on boot.
  3. Web page port / host name (default: port 80, `server_name _`), and whether to add nginx basic auth.
- Commands that need root: use `sudo`. If sudo asks for a password you cannot type, stop and give the user
  the exact commands to run.
- **Passwords:** generate them on the machine (`openssl rand -base64 24`), write them only into the two
  password files below, never into this repo, never into chat output, never into git.
- Do not change files in this repo for host-specific settings; host settings go into files outside it
  (password files, the systemd unit copy, the nginx site copy).
- Do not stop or kill Claude / tmux sessions that are already running on the machine (including your own).

## 0. Prerequisites

```bash
sudo apt update
sudo apt install -y tmux mariadb-server nginx php-fpm php-mysql python3-pymysql git openssl
```

- Claude Code must be installed with the native installer for the session user (`~/.local/bin/claude`) and
  logged in. Check: `~/.local/bin/claude --version`. If it is missing, tell the user and stop.
- The repo must live at `~/tmux-claude-sessions` of the session user (the systemd unit expects that path):
  `git clone <this repo url> ~/tmux-claude-sessions`. If it was cloned elsewhere, move it or symlink it.
- Note the PHP version for nginx: `ls /run/php/` (e.g. `php8.4-fpm.sock`).

## 1. Database

```bash
cd ~/tmux-claude-sessions
sudo mariadb < db/schema.sql
```

Create the two users. Everything is on this machine, so the agent host is `localhost`:

```bash
AGENT_PASS=$(openssl rand -base64 24 | tr -d '/+=')
WEB_PASS=$(openssl rand -base64 24 | tr -d '/+=')
sed -e "s/AGENT_HOST_IP/localhost/g" -e "s/CHANGE_ME_AGENT/$AGENT_PASS/" -e "s/CHANGE_ME_WEB/$WEB_PASS/" db/users.sql \
  | sudo mariadb
```

Store the passwords (same shell, before the variables are gone):

```bash
mkdir -p ~/.config/tmux-claude-sessions
printf '%s' "$AGENT_PASS" > ~/.config/tmux-claude-sessions/db.pass
chmod 600 ~/.config/tmux-claude-sessions/db.pass

sudo mkdir -p /etc/claude_db
printf '%s' "$WEB_PASS" | sudo tee /etc/claude_db/tmux_web.pass > /dev/null
sudo chown root:www-data /etc/claude_db/tmux_web.pass
sudo chmod 640 /etc/claude_db/tmux_web.pass
unset AGENT_PASS WEB_PASS
```

Add the sessions the user asked for (one row each; `tmux_alias` = short tmux name, unique, no spaces):

```sql
INSERT INTO claude_db.tmux_sessions (sort_order, session_name, project_path, tmux_alias, start_on_boot, desired_state)
VALUES (1, 'main', '/home/<user>/projects/main', 'main', 1, 'stopped');
```

Run with `sudo mariadb`. Use `desired_state='stopped'`; the user starts them from the page.
Every project folder must exist (`mkdir -p` it if the user agrees).

Check: `mariadb -u tmux_agent -p"$(cat ~/.config/tmux-claude-sessions/db.pass)" claude_db -e 'SELECT * FROM tmux_sessions'`
(run it, but do not echo the password).

## 2. Web page

```bash
sudo mkdir -p /var/www/tmux
sudo cp ~/tmux-claude-sessions/web/index.html ~/tmux-claude-sessions/web/api.php /var/www/tmux/
sudo cp ~/tmux-claude-sessions/web/nginx-site.conf /etc/nginx/sites-available/tmux
```

Edit `/etc/nginx/sites-available/tmux` (the copy, not the repo file):
- `fastcgi_pass` -> the socket found in step 0.
- `server_name` / `listen` -> what the user chose. If this is the only site, use `server_name _;` and remove
  `/etc/nginx/sites-enabled/default`.
- Basic auth if the user wants it: `sudo apt install -y apache2-utils`, `sudo htpasswd -c /etc/nginx/tmux.htpasswd <name>`
  (the user types the password), then add to the `server` block:
  `auth_basic "tmux"; auth_basic_user_file /etc/nginx/tmux.htpasswd;`

```bash
sudo ln -sf /etc/nginx/sites-available/tmux /etc/nginx/sites-enabled/tmux
sudo nginx -t && sudo systemctl reload nginx
```

Check: `curl -s http://localhost/api.php` returns JSON with `"sessions"` (not `db connection failed`).
If basic auth is on, add `-u <name>`, or check `sudo tail /var/log/nginx/error.log`.

## 3. Agent (as the session user, not root)

```bash
mkdir -p ~/.config/systemd/user
cp ~/tmux-claude-sessions/agent/tmux-claude-sessions.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now tmux-claude-sessions
sudo loginctl enable-linger "$USER"     # keeps it running without a login and after reboot
```

Check:
- `systemctl --user status tmux-claude-sessions` is active.
- `journalctl --user -u tmux-claude-sessions -n 20` shows `table read, boot sessions set` and no `db error`.
- `curl -s http://localhost/api.php` now has a `host` object with this machine's hostname.

## 4. Trust the project folders

Each project folder must be trusted once in Claude Code, otherwise the session hangs on the trust prompt.
Either run `claude` once in that folder and accept, or set
`"projects": { "<path>": { "hasTrustDialogAccepted": true } }` in `~/.claude.json` of the session user
(edit carefully: back the file up first, keep it valid JSON, only add the key for the new folders).

## 5. Done

Tell the user the page URL (`http://<machine ip>/`, find the IP with `hostname -I`), the sessions you added,
and that new sessions are added with an `INSERT` like step 1. Remind them the page has no login unless basic
auth was added: keep it on the LAN / VPN.

## Updating later

```bash
cd ~/tmux-claude-sessions && git pull
sudo cp web/index.html web/api.php /var/www/tmux/
systemctl --user restart tmux-claude-sessions   # safe: running sessions are not touched
```

## Several machines

Install it separately on each machine, each with its own `claude_db` (all-in-one as above). Do not point two
agents at the same database: each agent manages every row in `tmux_sessions`.
