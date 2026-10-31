-- Sessions are added by hand (the page does not add or delete rows). Example:
INSERT INTO claude_db.tmux_sessions (sort_order, session_name, project_path, tmux_alias, start_on_boot, desired_state)
VALUES (1, 'main', '/home/me/projects/main', 'main', 1, 'running'),
       (2, 'website', '/home/me/projects/website', 'website', 0, 'stopped');
