<?php
declare(strict_types=1);

require_once __DIR__ . '/includes/layout.php';

$id   = (int) ($_GET['id'] ?? 0);
$book = $id > 0 ? bf_find_book($id) : null;

if (!$book) {
    http_response_code(404);
    bf_header('Book not found');
    ?>
    <div class="page-header">
      <h1>Book not found <small>404</small></h1>
    </div>
    <p>
      It was never ordered, or it has been cleared out.
      <a href="<?= url() ?>">Start a new book.</a>
    </p>
    <?php
    bf_footer();
    exit;
}

$spec   = bf_page_estimate((int) $book['chapter_count']);
$events = bf_book_events($id);
$isActive = !in_array($book['status'], ['done', 'failed'], true);

$stmt = db()->prepare(
    'SELECT c.chapter_no, c.title, c.is_answer_key, COUNT(q.id) AS q_count
     FROM chapters c
     LEFT JOIN questions q ON q.chapter_id = c.id
     WHERE c.book_id = ?
     GROUP BY c.id, c.chapter_no, c.title, c.is_answer_key
     ORDER BY c.chapter_no'
);
$stmt->execute([$id]);
$chapters = $stmt->fetchAll();

bf_header($book['title']);
?>

<div class="page-header">
  <h1><?= e($book['title']) ?>
    <small><?= e($book['theme_label']) ?> &middot; <?= e(ucfirst($book['difficulty'])) ?></small>
  </h1>
  <p class="lead">
    <a href="<?= url() ?>">&larr; Order another</a>
  </p>
</div>

<div class="row">
  <div class="col-md-8">

    <div class="panel panel-<?= $book['status'] === 'done' ? 'success' : ($book['status'] === 'failed' ? 'danger' : 'info') ?>"
         data-book-id="<?= (int) $id ?>" data-active="<?= $isActive ? '1' : '0' ?>"
         data-poll="<?= e(url('api/job_status.php')) ?>" id="build-panel">
      <div class="panel-heading">
        <h3 class="panel-title" id="status-label">
          <?= e(bf_status_label($book['status'])) ?>
        </h3>
      </div>
      <div class="panel-body">
        <p id="status-note" style="margin:0 0 15px; color:#666;">
          <?= e($book['stage_note']) ?>
        </p>

        <div class="progress <?= $isActive ? 'active' : '' ?>">
          <div class="progress-bar progress-bar-<?= bf_status_class($book['status']) ?>"
               id="progress-bar"
               style="width: <?= (int) $book['progress'] ?>%"
               role="progressbar"
               aria-valuenow="<?= (int) $book['progress'] ?>"
               aria-valuemin="0"
               aria-valuemax="100">
          </div>
        </div>

        <?php if ($book['status'] === 'failed'): ?>
          <div class="alert alert-danger" role="alert">
            <strong>The run stopped.</strong>
            <p><?= e((string) ($book['error_message'] ?? 'No reason recorded.')) ?></p>
            <form method="post" action="<?= url('retry.php') ?>" style="display:inline;">
              <input type="hidden" name="csrf" value="<?= e(csrf_token()) ?>">
              <input type="hidden" name="id" value="<?= (int) $id ?>">
              <button class="btn btn-sm btn-default" type="submit">Try again</button>
            </form>
          </div>
        <?php endif; ?>

        <?php if ($book['status'] === 'done'): ?>
          <div class="alert alert-success" id="download-block">
            <p style="margin:0;">
              <a class="btn btn-primary" href="<?= url('download.php?id=' . (int) $id) ?>">
                Download the PDF
              </a>
              <span style="margin-left:15px; color:#666;">
                <?= e(bf_human_bytes($book['pdf_bytes'] !== null ? (int) $book['pdf_bytes'] : null)) ?>
              </span>
            </p>
          </div>
        <?php endif; ?>
      </div>
    </div>

    <?php if ($chapters): ?>
      <div class="panel panel-default">
        <div class="panel-heading">
          <h3 class="panel-title">Contents</h3>
        </div>
        <table class="table table-condensed mb-0">
          <thead>
            <tr>
              <th style="width:40px;">#</th>
              <th>Chapter</th>
              <th style="width:120px; text-align:right;">Questions</th>
            </tr>
          </thead>
          <tbody>
            <?php foreach ($chapters as $chapter): ?>
              <tr <?= $chapter['is_answer_key'] ? 'class="info"' : '' ?>>
                <td><strong><?= (int) $chapter['chapter_no'] ?></strong></td>
                <td><?= e($chapter['title']) ?></td>
                <td style="text-align:right; color:#999;">
                  <?= $chapter['is_answer_key'] ? 'answers' : (int) $chapter['q_count'] ?>
                </td>
              </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
    <?php endif; ?>

    <div class="panel panel-default">
      <div class="panel-heading">
        <h3 class="panel-title">Build log</h3>
      </div>
      <ul class="log-window" id="log-list">
        <?php foreach ($events as $event): ?>
          <li data-level="<?= e($event['level']) ?>">
            <time class="log-time"><?= e(substr((string) $event['created_at'], 11, 8)) ?></time>
            <span><?= e($event['message']) ?></span>
          </li>
        <?php endforeach; ?>
      </ul>
    </div>

  </div>

  <div class="col-md-4">

    <div class="panel panel-default">
      <div class="panel-heading">
        <h3 class="panel-title">Spec</h3>
      </div>
      <p class="spec-formula">
        <?= (int) $book['chapter_count'] ?> chapters
        &times; <?= (int) $book['pages_per_chapter'] ?> pages
        &times; <?= (int) $book['questions_per_page'] ?> questions
      </p>
      <table class="table table-condensed spec-table mb-0">
        <tbody>
          <tr>
            <td>Total questions</td>
            <td class="spec-value"><?= (int) $spec['questions'] ?></td>
          </tr>
          <tr>
            <td>Question pages</td>
            <td class="spec-value"><?= (int) $spec['content_pages'] ?></td>
          </tr>
          <tr>
            <td>Answer key</td>
            <td class="spec-value"><?= (int) $spec['answer_pages'] ?></td>
          </tr>
          <tr class="active">
            <td><strong>Total pages</strong></td>
            <td class="spec-value"><strong><?= (int) $spec['total_pages'] ?></strong></td>
          </tr>
        </tbody>
      </table>
    </div>

  </div>
</div>

<?php bf_footer(); ?>
