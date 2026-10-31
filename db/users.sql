-- DB users for tmux-claude-sessions. Replace the CHANGE_ME passwords before running, never commit real ones.
-- Agent (runs on the machine with the Claude sessions; use 'localhost' if the DB is on the same machine):
CREATE USER IF NOT EXISTS 'tmux_agent'@'AGENT_HOST_IP' IDENTIFIED BY 'CHANGE_ME_AGENT';
GRANT SELECT, INSERT, UPDATE ON claude_db.tmux_sessions TO 'tmux_agent'@'AGENT_HOST_IP';
GRANT SELECT, INSERT, UPDATE ON claude_db.host_stats TO 'tmux_agent'@'AGENT_HOST_IP';
-- Web page (PHP on the web server):
CREATE USER IF NOT EXISTS 'tmux_web'@'localhost' IDENTIFIED BY 'CHANGE_ME_WEB';
GRANT SELECT, UPDATE ON claude_db.tmux_sessions TO 'tmux_web'@'localhost';
GRANT SELECT ON claude_db.host_stats TO 'tmux_web'@'localhost';
