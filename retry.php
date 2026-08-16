<?php
declare(strict_types=1);

require_once __DIR__ . '/includes/helpers.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST' || !csrf_check($_POST['csrf'] ?? null)) {
    redirect(url());
}

$id   = (int) ($_POST['id'] ?? 0);
$book = $id > 0 ? bf_find_book($id) : null;

if (!$book || $book['status'] !== 'failed') {
    redirect(url());
}

$pdo = db();
$pdo->beginTransaction();

// Chapters cascade to questions, so clearing chapters clears the lot.
$pdo->prepare('DELETE FROM chapters WHERE book_id = ?')->execute([$id]);
$pdo->prepare(
    'UPDATE books
     SET status = "queued", progress = 0, stage_note = "Requeued",
         error_message = NULL, worker_token = NULL, started_at = NULL, finished_at = NULL
     WHERE id = ?'
)->execute([$id]);
$pdo->prepare('INSERT INTO job_events (book_id, level, message) VALUES (?, "info", "Requeued by hand.")')
    ->execute([$id]);

$pdo->commit();

bf_spawn_worker($id);

redirect(url('book.php?id=' . $id));
