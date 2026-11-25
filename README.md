# Book Factory

## AI based book maker

Pick a theme, set a length, get a print-ready trivia PDF with the answer key bound in at the back.

PHP 8.5 + MySQL 9.7 + NGINX 1.31, no Composer and no PHP framework. Gemini is called from a small Python worker that runs alongside the web app rather than inside the request.

---

## How it fits together

```
browser ──► index.php  (order form)
              │  POST
              ▼
          create.php   validates, INSERTs a `books` row with status='queued',
              │        then fires off a background worker and redirects
              ▼
          book.php     polls api/job_status.php every 2.5s for progress + log
              ▲
              │  UPDATEs
        ai/worker.py   claims the job, calls Gemini, writes rows, renders the PDF
              │
              ▼
        storage/books/000012-my-book.pdf  ──► download.php
```

The web app never talks to Gemini. It only writes a queued row and reads status back, so a slow or failed generation can't hang a page load.

### Why a queue at all

A 5-chapter book is 150 questions across 6 Gemini calls. That's well past any sane `fastcgi_read_timeout`. The `books.status` column is the whole state machine:

`queued → researching → writing → rendering → done` (or `failed`)

Workers claim jobs with a conditional `UPDATE ... WHERE status='queued'` and a random token, so running two of them never double-builds a book.

### Book shape

The house standard lives in `includes/config.php`:

- 3 questions per page
- 10 pages per chapter → **30 questions per chapter**
- the answer key is added automatically as the last chapter, and is not counted in the chapter number you pick

Pagination is arithmetic, not flow — `ai/pdf.py` places questions into a fixed three-slot grid rather than letting a layout engine decide, which is what keeps "3 per page, 10 per chapter" exactly true.

---

## Setup

### 1. Files

```bash
cp -R bookfactory /opt/homebrew/opt/nginx/html/
cd /opt/homebrew/opt/nginx/html/bookfactory
chmod -R 775 storage
```

### 2. Database

```bash
mysql -u root -p < sql/schema.sql

mysql -u root -p -e "
CREATE USER IF NOT EXISTS 'bookfactory'@'127.0.0.1' IDENTIFIED BY 'pick-a-password';
GRANT SELECT, INSERT, UPDATE, DELETE ON book_factory.* TO 'bookfactory'@'127.0.0.1';
FLUSH PRIVILEGES;"
```

Put that password in `.env` as `DB_PASS`.

### 3. Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r ai/requirements.txt
```

If you use the venv, point `PYTHON_BIN` in `.env` at it:

```
PYTHON_BIN=/opt/homebrew/opt/nginx/html/bookfactory/.venv/bin/python3
```

Otherwise `pip3 install -r ai/requirements.txt` globally and use `which python3`.

### 4. NGINX + PHP-FPM

```bash
brew services start php
brew services start mysql

# add the include line described at the top of nginx/bookfactory.conf
nginx -t && brew services restart nginx
```

Then open <http://localhost:8080/bookfactory/>.

### 5. Smoke test

```bash
python3 ai/worker.py --once     # "Nothing queued." means DB + config are fine
```

Order a 1-chapter book from the UI. It should finish in under a minute.

---

## Running the worker

Two modes, pick one.

**Fire-and-forget (default).** `AUTO_SPAWN_WORKER=1` makes `create.php` shell out to `worker.py --once --book-id N` in the background. Nothing to keep running; the trade-off is one Python start-up per book and no visibility if `exec()` is disabled in your PHP build.

**Daemon.** Set `AUTO_SPAWN_WORKER=0` and keep a press warm:

```bash
python3 ai/worker.py --loop
```

Output from either mode lands in `storage/logs/worker.log`, and every step is also written to `job_events` so it shows up in the build log on the book page.

---

## AI Notes

For this verion I picked the model: `gemini-3.5-flash-lite`. 
You can change the model to anything you want by modifying `ai/gemini.py`.

Two things about this generation caught me out and are worth knowing before you tweak `ai/gemini.py`:

- **`temperature`, `top_p` and `top_k` are deprecated and ignored.** Later models will 400 on them. Consistency has to come from the system instruction instead, which is why `SYSTEM_WRITER` is so prescriptive.
- **Flash-Lite defaults to `thinking_level: "minimal"`.** Fine for the per-chapter writing pass, too shallow for research, so `GEMINI_THINKING_RESEARCH` is set to `medium`.

The research pass uses Google Search grounding so questions aren't invented from stale memory. If your key has no grounding quota the worker retries ungrounded automatically; set `GEMINI_USE_SEARCH=0` to skip the attempt.

Roughly one call per chapter plus one for research. A 5-chapter book is ~6 calls and a few cents.

### Keeping questions distinct

Duplicates are the obvious failure mode for a 150-question book. Three defences:

1. The research pass assigns each chapter a non-overlapping angle up front.
2. Every chapter prompt carries the questions and answers already used.
3. `worker.py` normalises and hashes both question and answer, drops collisions, and re-asks for the shortfall (up to 3 rounds) before giving up.

---

## Security notes for when this stops being local

Currently fine for localhost, would need work before exposure:

- **There's no auth.** Anyone reaching the port can spend your Gemini quota.
- **`.env` sits inside the web root.** The NGINX config denies it, but the safer fix is moving the whole app out of `html/` and pointing `root` at a `public/` subdirectory.
- **Rotate the API key** that was pasted into chat.
- CSRF tokens and prepared statements are in place; output is escaped through `e()`.

---

## Layout

```
bookfactory/
├── index.php              order form
├── create.php             validate + queue
├── book.php               progress, contents, build log, download
├── download.php           streams the PDF (checks status first)
├── retry.php              requeue a failed book
├── api/job_status.php     JSON polled by the book page
├── includes/
│   ├── config.php         .env loader, house standard constants
│   ├── db.php             PDO singleton
│   ├── helpers.php        escaping, CSRF, worker spawn, page maths
│   └── layout.php         header/footer partials
├── assets/css/style.css
├── assets/js/app.js       live imposition readout + progress polling
├── ai/
│   ├── worker.py          the job runner
│   ├── gemini.py          prompts, schemas, retries
│   ├── pdf.py             typesetting
│   ├── bfconfig.py        shared .env + MySQL
│   └── requirements.txt
├── sql/schema.sql
├── nginx/bookfactory.conf
└── storage/books/         generated PDFs (gitignored)
```
