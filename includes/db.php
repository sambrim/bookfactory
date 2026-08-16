<?php
declare(strict_types=1);

require_once __DIR__ . '/config.php';

function db(): PDO
{
    static $pdo = null;
    if ($pdo instanceof PDO) {
        return $pdo;
    }

    $dsn = sprintf(
        'mysql:host=%s;port=%s;dbname=%s;charset=utf8mb4',
        cfg('DB_HOST', '127.0.0.1'),
        cfg('DB_PORT', '3306'),
        cfg('DB_NAME', 'book_factory')
    );

    try {
        $pdo = new PDO($dsn, (string) cfg('DB_USER'), (string) cfg('DB_PASS'), [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES   => false,
        ]);
    } catch (PDOException $e) {
        http_response_code(500);
        $detail = cfg_bool('APP_DEBUG') ? ' — ' . $e->getMessage() : '';
        exit('Database connection failed' . $detail);
    }

    return $pdo;
}
