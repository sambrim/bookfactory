<?php
declare(strict_types=1);

require_once __DIR__ . '/includes/helpers.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    redirect(url());
}

bf_session_start();

if (!csrf_check($_POST['csrf'] ?? null)) {
    $_SESSION['form_errors'] = ['The form expired. Try again.'];
    redirect(url());
}

$title       = trim((string) ($_POST['title'] ?? ''));
$themeSlug   = trim((string) ($_POST['theme'] ?? ''));
$customTheme = trim((string) ($_POST['custom_theme'] ?? ''));
$chapters    = (int) ($_POST['chapters'] ?? 0);
$difficulty  = (string) ($_POST['difficulty'] ?? 'mixed');

$errors = [];

if (mb_strlen($title) < 3) {
    $errors[] = 'Give the book a title of at least 3 characters.';
}
if (mb_strlen($title) > 200) {
    $errors[] = 'Titles cap out at 200 characters.';
}

/* ---------------------------------------------------------------------------
 * Theme. Either a preset from the themes table, or free text the person typed.
 * The custom label ends up inside a Gemini prompt, so strip control characters
 * and newlines that would let it break out of the line it belongs on.
 * ------------------------------------------------------------------------- */
$themeLabel = null;

if ($themeSlug === BF_CUSTOM_THEME) {
    $customTheme = preg_replace('/[\x00-\x1F\x7F]+/u', ' ', $customTheme) ?? '';
    $customTheme = trim(preg_replace('/\s+/u', ' ', $customTheme) ?? '');

    if (mb_strlen($customTheme) < 3) {
        $errors[] = 'Type a theme of at least 3 characters, or pick one from the list.';
    } elseif (mb_strlen($customTheme) > 120) {
        $errors[] = 'Custom themes cap out at 120 characters.';
    } else {
        $themeLabel = $customTheme;
    }
} else {
    $stmt = db()->prepare('SELECT name FROM themes WHERE slug = ? AND is_active = 1');
    $stmt->execute([$themeSlug]);
    $found = $stmt->fetchColumn();

    if ($found === false) {
        $errors[] = 'Pick a theme from the list.';
    } else {
        $themeLabel = (string) $found;
    }
}

if ($chapters < BF_MIN_CHAPTERS || $chapters > BF_MAX_CHAPTERS) {
    $errors[] = sprintf('Chapters must be between %d and %d.', BF_MIN_CHAPTERS, BF_MAX_CHAPTERS);
}

if (!in_array($difficulty, ['easy', 'mixed', 'hard'], true)) {
    $difficulty = 'mixed';
}

if ($errors) {
    $_SESSION['form_errors'] = $errors;
    $_SESSION['form_old'] = [
        'title'        => $title,
        'theme'        => $themeSlug,
        'custom_theme' => $customTheme,
        'chapters'     => $chapters,
        'difficulty'   => $difficulty,
    ];
    redirect(url());
}

$insert = db()->prepare(
    'INSERT INTO books
       (title, theme_slug, theme_label, difficulty, chapter_count,
        pages_per_chapter, questions_per_page, status, stage_note)
     VALUES (?, ?, ?, ?, ?, ?, ?, "queued", "Waiting for a free press")'
);
$insert->execute([
    $title,
    $themeSlug,
    (string) $themeLabel,
    $difficulty,
    $chapters,
    BF_PAGES_PER_CHAPTER,
    BF_QUESTIONS_PER_PAGE,
]);

$bookId = (int) db()->lastInsertId();

$log = db()->prepare('INSERT INTO job_events (book_id, level, message) VALUES (?, "info", ?)');
$log->execute([
    $bookId,
    sprintf(
        'Order placed: %s, %d chapters, %s difficulty.',
        $themeLabel,
        $chapters,
        $difficulty
    ),
]);

bf_spawn_worker($bookId);

redirect(url('book.php?id=' . $bookId));
