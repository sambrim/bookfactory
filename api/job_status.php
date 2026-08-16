<?php
declare(strict_types=1);

require_once dirname(__DIR__) . '/includes/helpers.php';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

$id   = (int) ($_GET['id'] ?? 0);
$book = $id > 0 ? bf_find_book($id) : null;

if (!$book) {
    http_response_code(404);
    echo json_encode(['error' => 'No book with that id.']);
    exit;
}

$after = (int) ($_GET['after'] ?? 0);

$stmt = db()->prepare(
    'SELECT id, level, message, created_at FROM job_events
     WHERE book_id = ? AND id > ? ORDER BY id LIMIT 100'
);
$stmt->execute([$id, $after]);
$events = $stmt->fetchAll();

echo json_encode([
    'id'        => (int) $book['id'],
    'status'    => $book['status'],
    'label'     => bf_status_label($book['status']),
    'progress'  => (int) $book['progress'],
    'note'      => $book['stage_note'],
    'error'     => $book['error_message'],
    'done'      => $book['status'] === 'done',
    'failed'    => $book['status'] === 'failed',
    'filesize'  => bf_human_bytes($book['pdf_bytes'] !== null ? (int) $book['pdf_bytes'] : null),
    'events'    => array_map(static fn(array $row): array => [
        'id'      => (int) $row['id'],
        'level'   => $row['level'],
        'message' => $row['message'],
        'time'    => substr((string) $row['created_at'], 11, 8),
    ], $events),
], JSON_UNESCAPED_UNICODE);
