<?php
// JSON API for claude_db.tmux_sessions (keep it LAN only / behind auth).
// The page only writes desired_state / update_requested / settings / row order (rows are added and removed by hand, not here); tmux-claude-sessions does the real start/stop.
header('Content-Type: application/json');

function out($data, $code = 200) {
    http_response_code($code);
    echo json_encode($data);
    exit;
}

try {
    $pass = trim(file_get_contents('/etc/claude_db/tmux_web.pass'));
    $db = new PDO('mysql:host=localhost;dbname=claude_db;charset=utf8mb4', 'tmux_web', $pass,
                  [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]);
} catch (Exception $e) {
    out(['error' => 'db connection failed'], 500);
}

if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    $rows = $db->query('SELECT id, session_name, project_path, tmux_alias, start_on_boot, desired_state, actual_state, '
                       . 'rss_mb, claude_version, update_requested, last_seen, last_error, TIMESTAMPDIFF(SECOND, last_seen, NOW()) AS seen_ago '
                       . 'FROM tmux_sessions ORDER BY sort_order, id')->fetchAll();
    $host = $db->query('SELECT host, cpu_pct, mem_used_mb, mem_total_mb, swap_used_mb, claude_latest, '
                       . 'TIMESTAMPDIFF(SECOND, updated_at, NOW()) AS age FROM host_stats ORDER BY updated_at DESC LIMIT 1')->fetch();
    out(['sessions' => $rows, 'host' => $host ?: null]);
}

// Writes need the custom header, so a plain cross-site form post cannot change anything
if ($_SERVER['REQUEST_METHOD'] !== 'POST' || ($_SERVER['HTTP_X_TMUX_WEB'] ?? '') !== '1') {
    out(['error' => 'bad request'], 400);
}
$in = json_decode(file_get_contents('php://input'), true) ?: [];
$action = $in['action'] ?? '';
$id = (int)($in['id'] ?? 0);

try {
    switch ($action) {
        case 'state':   // on/off
            $state = ($in['state'] ?? '') === 'running' ? 'running' : 'stopped';
            $db->prepare('UPDATE tmux_sessions SET desired_state=? WHERE id=?')->execute([$state, $id]);
            break;
        case 'update':  // restart on the newest installed Claude Code (--continue); the agent clears the flag
            $db->prepare('UPDATE tmux_sessions SET update_requested=1 WHERE id=? AND desired_state=\'running\'')->execute([$id]);
            break;
        case 'boot':
            $db->prepare('UPDATE tmux_sessions SET start_on_boot=? WHERE id=?')->execute([empty($in['on']) ? 0 : 1, $id]);
            break;
        case 'reorder':   // drag handle: ids in their new order
            $st = $db->prepare('UPDATE tmux_sessions SET sort_order=? WHERE id=?');
            $db->beginTransaction();
            foreach (array_values((array)($in['ids'] ?? [])) as $i => $rid) $st->execute([$i + 1, (int)$rid]);
            $db->commit();
            break;
        default:
            out(['error' => 'unknown action'], 400);
    }
} catch (PDOException $e) {
    out(['error' => 'db error'], 409);
}
out(['ok' => true]);
