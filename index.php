<?php
declare(strict_types=1);

require_once __DIR__ . '/includes/layout.php';

$themes = bf_themes();
$recent = bf_recent_books(6);

bf_session_start();
$errors = $_SESSION['form_errors'] ?? [];
$old    = $_SESSION['form_old'] ?? [];
unset($_SESSION['form_errors'], $_SESSION['form_old']);

$defaultChapters = (int) ($old['chapters'] ?? 5);
$selectedTheme   = (string) ($old['theme'] ?? '');
$customTheme     = (string) ($old['custom_theme'] ?? '');
$isCustom        = $selectedTheme === BF_CUSTOM_THEME;

bf_header('New book');
?>

<div class="page-header">
  <h1>New book <small>set the spec and start the run</small></h1>
</div>

<p class="lead">
  Pick a theme and a length. Book Factory researches the subject, writes the
  questions, and produces a print-ready PDF with the answer key at the back.
</p>

<?php if ($errors): ?>
  <div class="alert alert-danger">
    <h4>The order was not submitted</h4>
    <ul>
      <?php foreach ($errors as $error): ?>
        <li><?= e($error) ?></li>
      <?php endforeach; ?>
    </ul>
  </div>
<?php endif; ?>

<form method="post" action="<?= url('create.php') ?>" id="order-form">
  <input type="hidden" name="csrf" value="<?= e(csrf_token()) ?>">

  <div class="row">
    <div class="col-md-8">

      <div class="panel panel-default">
        <div class="panel-heading">
          <h3 class="panel-title">Book details</h3>
        </div>
        <div class="panel-body">

          <div class="form-group">
            <label class="control-label" for="theme">Theme</label>
            <select class="form-control" id="theme" name="theme">
              <?php foreach ($themes as $theme): ?>
                <option value="<?= e($theme['slug']) ?>"
                  <?= $selectedTheme === $theme['slug'] ? 'selected' : '' ?>>
                  <?= e($theme['name']) ?> &mdash; <?= e($theme['blurb']) ?>
                </option>
              <?php endforeach; ?>
              <option value="<?= e(BF_CUSTOM_THEME) ?>" <?= $isCustom ? 'selected' : '' ?>>
                Something else (type your own)&hellip;
              </option>
            </select>
            <span class="help-block">What the whole book is about.</span>
          </div>

          <div class="form-group <?= $isCustom ? '' : 'hidden' ?>" id="custom-theme-group">
            <label class="control-label" for="custom_theme">Your theme</label>
            <input type="text" class="form-control" id="custom_theme" name="custom_theme"
                   maxlength="120" autocomplete="off"
                   placeholder="Formula 1 in the 1990s"
                   value="<?= e($customTheme) ?>">
            <span class="help-block">
              Be specific &mdash; &ldquo;Norwegian black metal&rdquo; makes a much better book
              than &ldquo;music&rdquo;. 3 to 120 characters.
            </span>
          </div>

          <div class="form-group">
            <label class="control-label" for="title">Book title</label>
            <input type="text" class="form-control input-lg" id="title" name="title"
                   maxlength="200" required autocomplete="off"
                   placeholder="The Second Book of Impossible Questions"
                   value="<?= e($old['title'] ?? '') ?>">
            <span class="help-block">Printed on the cover. 3 to 200 characters.</span>
          </div>

          <div class="form-group">
            <label class="control-label" for="chapters">Chapters</label>
            <input type="number" class="form-control input-narrow" id="chapters" name="chapters"
                   min="<?= BF_MIN_CHAPTERS ?>" max="<?= BF_MAX_CHAPTERS ?>" step="1"
                   value="<?= e((string) $defaultChapters) ?>" required>
            <span class="help-block">
              Content chapters only, <?= BF_MIN_CHAPTERS ?>&ndash;<?= BF_MAX_CHAPTERS ?>.
              The answer key is added automatically as the last chapter.
            </span>
          </div>

          <div class="form-group mb-0">
            <span class="control-label">Difficulty</span>
            <div>
              <?php
              $levels = ['easy' => 'Easy', 'mixed' => 'Mixed', 'hard' => 'Hard'];
              foreach ($levels as $value => $label):
                  $checked = ($old['difficulty'] ?? 'mixed') === $value;
                  ?>
                <label class="radio-inline">
                  <input type="radio" name="difficulty" value="<?= e($value) ?>"
                    <?= $checked ? 'checked' : '' ?>> <?= e($label) ?>
                </label>
              <?php endforeach; ?>
            </div>
            <span class="help-block">How hard the questions should skew.</span>
          </div>

        </div>
        <div class="panel-footer">
          <button type="submit" class="btn btn-primary btn-lg" id="submit-btn">
            Start the print run
          </button>
          <span class="text-muted" style="margin-left:10px;">
            Roughly a minute per chapter.
          </span>
        </div>
      </div>

    </div>
    <div class="col-md-4">

      <div class="panel panel-default" id="spec-sheet"
           data-qpp="<?= BF_QUESTIONS_PER_PAGE ?>"
           data-ppc="<?= BF_PAGES_PER_CHAPTER ?>">
        <div class="panel-heading">
          <h3 class="panel-title">What you&rsquo;ll get</h3>
        </div>
        <p class="spec-formula">
          <span id="spec-chapters"><?= (int) $defaultChapters ?></span> chapters
          &times; <?= BF_PAGES_PER_CHAPTER ?> pages
          &times; <?= BF_QUESTIONS_PER_PAGE ?> questions
        </p>
        <table class="table table-condensed spec-table" aria-live="polite">
          <tbody>
            <tr>
              <td>Questions</td>
              <td class="spec-value" id="spec-questions">&mdash;</td>
            </tr>
            <tr>
              <td>Question pages</td>
              <td class="spec-value" id="spec-content">&mdash;</td>
            </tr>
            <tr>
              <td>Answer key pages</td>
              <td class="spec-value" id="spec-answers">&mdash;</td>
            </tr>
            <tr class="active">
              <td>Total pages</td>
              <td class="spec-value" id="spec-total">&mdash;</td>
            </tr>
          </tbody>
        </table>
        <div class="panel-footer">
          Cover and contents page included in the total.
        </div>
      </div>

    </div>
  </div>
</form>

<?php if ($recent): ?>
  <div class="panel panel-default">
    <div class="panel-heading">
      <h3 class="panel-title">Recent books</h3>
    </div>
    <div class="list-group">
      <?php foreach ($recent as $book): ?>
        <div class="list-group-item">
          <?php if ($book['status'] === 'queued'): ?>
            <form method="post" action="<?= url('cancel.php') ?>" style="float:right; margin:0;">
              <input type="hidden" name="csrf" value="<?= e(csrf_token()) ?>">
              <input type="hidden" name="id" value="<?= (int) $book['id'] ?>">
              <button type="submit" class="btn btn-sm btn-default"
                      onclick="return confirm('Delete this queued book?');">
                Cancel
              </button>
            </form>
          <?php endif; ?>
          
          <a href="<?= url('book.php?id=' . (int) $book['id']) ?>" style="color:inherit; text-decoration:none;">
            <span class="label label-<?= e(bf_status_class($book['status'])) ?>"
                  style="float:right; margin-right:10px;">
              <?= e(bf_status_label($book['status'])) ?>
              <?php if (!in_array($book['status'], ['done', 'failed'], true)): ?>
                <?= (int) $book['progress'] ?>%
              <?php endif; ?>
            </span>
            <h4 class="list-group-item-heading" style="margin:0 0 5px;"><?= e($book['title']) ?></h4>
            <p class="list-group-item-text" style="margin:0;">
              <?= e($book['theme_label']) ?> &middot;
              <?= (int) $book['chapter_count'] ?> chapters &middot;
              <?= e(substr((string) $book['created_at'], 0, 16)) ?>
            </p>
          </a>
        </div>
      <?php endforeach; ?>
    </div>
  </div>
<?php endif; ?>

<?php bf_footer(); ?>
