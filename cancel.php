<?php
declare(strict_types=1);

require_once __DIR__ . '/includes/helpers.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST' || !csrf_check($_POST['csrf'] ?? null)) {
    redirect(url());
}

$id   = (int) ($_POST['id'] ?? 0);
$book = $id > 0 ? bf_find_book($id) : null;

if (!$book || $book['status'] !== 'queued') {
    redirect(url());
}

db()->prepare('DELETE FROM books WHERE id = ?')->execute([$id]);

redirect(url());
