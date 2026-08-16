<?php
declare(strict_types=1);

require_once __DIR__ . '/helpers.php';

function bf_header(string $title): void
{
    ?><!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= e($title) ?> &middot; Book Factory</title>
<link rel="stylesheet" href="<?= url('assets/css/style.css') ?>">
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>

<div class="navbar">
  <div class="container">
    <a class="navbar-brand" href="<?= url() ?>">Book Factory</a>
    <span class="navbar-text">Trivia book generator</span>
    <span class="navbar-right">3 questions/page &middot; 10 pages/chapter</span>
  </div>
</div>

<div class="container" id="main">
<?php
}

function bf_footer(): void
{
    ?>
</div><!-- /.container -->

<div class="footer">
  <div class="container">
    <p>
      Book Factory &middot; local development build
      <span class="pull-right">Answer key is always the last chapter</span>
    </p>
  </div>
</div>

<script src="<?= url('assets/js/app.js') ?>"></script>
</body>
</html>
<?php
}
