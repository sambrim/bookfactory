<?php
declare(strict_types=1);

require_once __DIR__ . '/db.php';

/** Escape for HTML output. */
function e(?string $value): string
{
    return htmlspecialchars((string) $value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function bf_session_start(): void
{
    if (session_status() === PHP_SESSION_NONE) {
        session_start();
    }
}

function csrf_token(): string
{
    bf_session_start();
    if (empty($_SESSION['csrf'])) {
        $_SESSION['csrf'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf'];
}

function csrf_check(?string $token): bool
{
    bf_session_start();
    return is_string($token)
        && !empty($_SESSION['csrf'])
        && hash_equals($_SESSION['csrf'], $token);
}

function redirect(string $path): never
{
    header('Location: ' . $path);
    exit;
}

/** Themes for the picker. */
function bf_themes(): array
{
    return db()
        ->query('SELECT slug, name, blurb FROM themes WHERE is_active = 1 ORDER BY sort_order, name')
        ->fetchAll();
}

function bf_find_book(int $id): ?array
{
    $stmt = db()->prepare('SELECT * FROM books WHERE id = ?');
    $stmt->execute([$id]);
    $book = $stmt->fetch();
    return $book ?: null;
}

function bf_recent_books(int $limit = 12): array
{
    $stmt = db()->prepare(
        'SELECT id, title, theme_label, chapter_count, status, progress, created_at, pdf_path
         FROM books ORDER BY id DESC LIMIT ?'
    );
    $stmt->bindValue(1, $limit, PDO::PARAM_INT);
    $stmt->execute();
    return $stmt->fetchAll();
}

function bf_book_events(int $bookId, int $limit = 40): array
{
    $stmt = db()->prepare(
        'SELECT level, message, created_at FROM job_events
         WHERE book_id = ? ORDER BY id DESC LIMIT ?'
    );
    $stmt->bindValue(1, $bookId, PDO::PARAM_INT);
    $stmt->bindValue(2, $limit, PDO::PARAM_INT);
    $stmt->execute();
    return array_reverse($stmt->fetchAll());
}

/**
 * Total printed pages: cover + contents + content pages + answer key pages.
 * The answer key packs 2 columns × 30 lines, so it needs far fewer pages.
 */
function bf_page_estimate(int $chapters): array
{
    $questions   = $chapters * bf_questions_per_chapter();
    $contentPgs  = $chapters * BF_PAGES_PER_CHAPTER;
    $answerPgs   = max(1, (int) ceil($questions / 60));
    return [
        'questions'     => $questions,
        'content_pages' => $contentPgs,
        'answer_pages'  => $answerPgs,
        'total_pages'   => 2 + $contentPgs + $answerPgs,
    ];
}

/**
 * Kick off a one-shot worker in the background so the request returns straight
 * away. No-op when AUTO_SPAWN_WORKER=0 (you're running the daemon instead).
 */
function bf_spawn_worker(int $bookId): bool
{
    if (!cfg_bool('AUTO_SPAWN_WORKER', true)) {
        return false;
    }

    $python = (string) cfg('PYTHON_BIN', '/usr/bin/python3');
    $script = BF_ROOT . '/ai/worker.py';
    $log    = BF_ROOT . '/storage/logs/worker.log';

    if (!is_file($script)) {
        return false;
    }

    $cmd = sprintf(
        '%s %s --once --book-id %d >> %s 2>&1 &',
        escapeshellarg($python),
        escapeshellarg($script),
        $bookId,
        escapeshellarg($log)
    );

    // exec() is often disabled in hardened PHP builds; fail soft.
    if (!function_exists('exec')) {
        return false;
    }
    @exec($cmd);
    return true;
}

function bf_status_label(string $status): string
{
    return match ($status) {
        'queued'      => 'Queued',
        'researching' => 'Researching the theme',
        'writing'     => 'Writing questions',
        'rendering'   => 'Typesetting the PDF',
        'done'        => 'Ready',
        'failed'      => 'Failed',
        default       => ucfirst($status),
    };
}

/** Maps a job status onto a .label-* / .progress-bar-* suffix. */
function bf_status_class(string $status): string
{
    return match ($status) {
        'done'   => 'success',
        'failed' => 'danger',
        'queued' => 'default',
        default  => 'info',
    };
}

function bf_human_bytes(?int $bytes): string
{
    if (!$bytes) {
        return '—';
    }
    $units = ['B', 'KB', 'MB'];
    $i = 0;
    $n = (float) $bytes;
    while ($n >= 1024 && $i < count($units) - 1) {
        $n /= 1024;
        $i++;
    }
    return round($n, $i === 0 ? 0 : 1) . ' ' . $units[$i];
}
