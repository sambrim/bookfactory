<?php
declare(strict_types=1);

/**
 * Loads .env and exposes it through cfg(). No framework, no autoloader.
 */

define('BF_ROOT', dirname(__DIR__));

function bf_load_env(string $path): array
{
    if (!is_readable($path)) {
        http_response_code(500);
        exit('Missing .env — copy .env.example to .env and fill it in.');
    }

    $env = [];
    foreach (file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
        $line = trim($line);
        if ($line === '' || $line[0] === '#') {
            continue;
        }
        $parts = explode('=', $line, 2);
        if (count($parts) !== 2) {
            continue;
        }
        $key = trim($parts[0]);
        $val = trim($parts[1]);
        // strip matching quotes
        if (strlen($val) > 1 && ($val[0] === '"' || $val[0] === "'") && $val[-1] === $val[0]) {
            $val = substr($val, 1, -1);
        }
        $env[$key] = $val;
    }
    return $env;
}

$GLOBALS['BF_ENV'] = bf_load_env(BF_ROOT . '/.env');

function cfg(string $key, mixed $default = null): mixed
{
    return $GLOBALS['BF_ENV'][$key] ?? $default;
}

function cfg_bool(string $key, bool $default = false): bool
{
    $raw = cfg($key);
    if ($raw === null) {
        return $default;
    }
    return in_array(strtolower((string) $raw), ['1', 'true', 'yes', 'on'], true);
}

/** Absolute path to the PDF storage directory. */
function bf_storage_path(): string
{
    $configured = (string) cfg('STORAGE_PATH', 'storage/books');
    $path = str_starts_with($configured, '/')
        ? $configured
        : BF_ROOT . '/' . ltrim($configured, '/');

    if (!is_dir($path)) {
        mkdir($path, 0775, true);
    }
    return rtrim($path, '/');
}

/**
 * URL prefix the app is served under, e.g. "/bookfactory". Empty when it sits
 * at the document root. Set APP_BASE in .env to override.
 */
function bf_base(): string
{
    return rtrim((string) cfg('APP_BASE', '/bookfactory'), '/');
}

/** Build an absolute-from-root URL. */
function url(string $path = ''): string
{
    return bf_base() . '/' . ltrim($path, '/');
}

/* ---------------------------------------------------------------------------
 * House standard for a Book Factory book. Change here, not in the templates.
 * ------------------------------------------------------------------------- */
const BF_QUESTIONS_PER_PAGE = 3;
const BF_PAGES_PER_CHAPTER  = 10;
const BF_MIN_CHAPTERS       = 1;
const BF_MAX_CHAPTERS       = 12;

/**
 * theme_slug stored when the person types their own subject instead of picking
 * a preset. The typed text lives in books.theme_label, which is all the worker
 * actually reads, so nothing downstream needs to know the difference.
 */
const BF_CUSTOM_THEME = '__custom__';

function bf_questions_per_chapter(): int
{
    return BF_QUESTIONS_PER_PAGE * BF_PAGES_PER_CHAPTER;
}

if (cfg_bool('APP_DEBUG')) {
    ini_set('display_errors', '1');
    error_reporting(E_ALL);
} else {
    ini_set('display_errors', '0');
}

date_default_timezone_set('UTC');
