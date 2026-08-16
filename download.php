<?php
declare(strict_types=1);

require_once __DIR__ . '/includes/helpers.php';

$id   = (int) ($_GET['id'] ?? 0);
$book = $id > 0 ? bf_find_book($id) : null;

if (!$book || $book['status'] !== 'done' || !$book['pdf_path']) {
    http_response_code(404);
    exit('That PDF is not ready.');
}

// pdf_path is stored as a bare filename; refuse anything that looks like a path.
$name = basename((string) $book['pdf_path']);
$file = bf_storage_path() . '/' . $name;

if (!is_file($file) || !is_readable($file)) {
    http_response_code(410);
    exit('The file is gone from storage. Run the book again.');
}

$download = preg_replace('/[^A-Za-z0-9 _.-]/', '', $book['title']) ?: 'book';
$download = trim($download) . '.pdf';

header('Content-Type: application/pdf');
header('Content-Length: ' . filesize($file));
header('Content-Disposition: attachment; filename="' . $download . '"');
header('X-Content-Type-Options: nosniff');

readfile($file);
