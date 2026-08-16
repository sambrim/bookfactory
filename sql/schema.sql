-- Book Factory — schema
-- Run: mysql -u root -p < sql/schema.sql

CREATE DATABASE IF NOT EXISTS book_factory
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE book_factory;

-- ---------------------------------------------------------------------------
-- Themes shown in the picker. Seeded below, add your own freely.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS themes (
  id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  slug        VARCHAR(64)  NOT NULL,
  name        VARCHAR(128) NOT NULL,
  blurb       VARCHAR(255) NOT NULL DEFAULT '',
  sort_order  INT          NOT NULL DEFAULT 100,
  is_active   TINYINT(1)   NOT NULL DEFAULT 1,
  PRIMARY KEY (id),
  UNIQUE KEY uq_themes_slug (slug)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- One row per book. `status` drives the whole pipeline.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS books (
  id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  title               VARCHAR(200) NOT NULL,
  theme_slug          VARCHAR(64)  NOT NULL,
  theme_label         VARCHAR(128) NOT NULL,
  difficulty          ENUM('easy','mixed','hard') NOT NULL DEFAULT 'mixed',

  -- Book shape. Defaults match the house standard.
  chapter_count       TINYINT UNSIGNED NOT NULL DEFAULT 5,   -- content chapters, answer key excluded
  pages_per_chapter   TINYINT UNSIGNED NOT NULL DEFAULT 10,
  questions_per_page  TINYINT UNSIGNED NOT NULL DEFAULT 3,

  status              ENUM('queued','researching','writing','rendering','done','failed')
                        NOT NULL DEFAULT 'queued',
  progress            TINYINT UNSIGNED NOT NULL DEFAULT 0,   -- 0-100
  stage_note          VARCHAR(255) NOT NULL DEFAULT '',
  error_message       TEXT NULL,

  research_brief      MEDIUMTEXT NULL,   -- what the model found out about the theme
  pdf_path            VARCHAR(255) NULL, -- relative to storage/books
  pdf_bytes           INT UNSIGNED NULL,

  worker_token        CHAR(32) NULL,     -- set when a worker claims the job
  created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  started_at          DATETIME NULL,
  finished_at         DATETIME NULL,

  PRIMARY KEY (id),
  KEY idx_books_status (status, id),
  KEY idx_books_created (created_at)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Chapters. The answer key is stored as a normal chapter with is_answer_key=1
-- and always sorts last.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chapters (
  id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  book_id        BIGINT UNSIGNED NOT NULL,
  chapter_no     TINYINT UNSIGNED NOT NULL,
  title          VARCHAR(200) NOT NULL,
  intro          TEXT NULL,
  is_answer_key  TINYINT(1) NOT NULL DEFAULT 0,
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_chapter_no (book_id, chapter_no),
  CONSTRAINT fk_chapters_book FOREIGN KEY (book_id)
    REFERENCES books (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Questions. global_no is the number printed in the book and referenced by the
-- answer key, so it must be unique per book.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS questions (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  book_id      BIGINT UNSIGNED NOT NULL,
  chapter_id   BIGINT UNSIGNED NOT NULL,
  global_no    SMALLINT UNSIGNED NOT NULL,
  chapter_no   TINYINT UNSIGNED NOT NULL,
  position     SMALLINT UNSIGNED NOT NULL,  -- 1..30 within the chapter
  question     TEXT NOT NULL,
  answer       TEXT NOT NULL,
  fun_fact     TEXT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_question_global (book_id, global_no),
  KEY idx_questions_chapter (chapter_id, position),
  CONSTRAINT fk_questions_book FOREIGN KEY (book_id)
    REFERENCES books (id) ON DELETE CASCADE,
  CONSTRAINT fk_questions_chapter FOREIGN KEY (chapter_id)
    REFERENCES chapters (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Build log. Surfaced on the book page so failures are debuggable from the UI.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS job_events (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  book_id     BIGINT UNSIGNED NOT NULL,
  level       ENUM('info','warn','error') NOT NULL DEFAULT 'info',
  message     VARCHAR(500) NOT NULL,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_events_book (book_id, id),
  CONSTRAINT fk_events_book FOREIGN KEY (book_id)
    REFERENCES books (id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Seed themes
-- ---------------------------------------------------------------------------
INSERT INTO themes (slug, name, blurb, sort_order) VALUES
  ('general-knowledge', 'General knowledge',  'A bit of everything, pub-quiz style.',            10),
  ('world-history',     'World history',      'Empires, revolutions, treaties and turning points.', 20),
  ('geography',         'Geography',          'Capitals, rivers, borders and odd little places.',   30),
  ('science-nature',    'Science & nature',   'Physics, chemistry, biology and the animal kingdom.', 40),
  ('space',             'Space & astronomy',  'Planets, missions, telescopes and deep sky.',        50),
  ('film-tv',           'Film & television',  'Directors, casts, box office and cult classics.',    60),
  ('music',             'Music',              'Charts, bands, instruments and one-hit wonders.',    70),
  ('sport',             'Sport',              'Records, rules, rivalries and famous finals.',       80),
  ('food-drink',        'Food & drink',       'Dishes, ingredients, origins and drinking customs.', 90),
  ('literature',        'Literature',         'Novels, poets, first lines and literary prizes.',   100),
  ('technology',        'Technology',         'Computing, the internet and the people behind it.', 110),
  ('mythology',         'Myths & legends',    'Gods, monsters and folklore from around the world.', 120)
ON DUPLICATE KEY UPDATE
  name = VALUES(name), blurb = VALUES(blurb), sort_order = VALUES(sort_order);
