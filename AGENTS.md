# AGENTS.md

Christmas points race ("Puntos Navideños") for Sala de Videojuegos Deybis. Django project, single app, Spanish-language UI.

**The app is no longer a raffle.** Players accumulate points (1 point per hour played) and the **top N** of the leaderboard (N is configurable, see below) each receive a prize on **December 25**. There are no ticket numbers and no daily draw.

## Layout

- `rifapp/` — project config only (`settings.py`, `urls.py`, `wsgi.py`, `asgi.py`). Root URLconf mounts `points.urls` at `/` and `admin/` at `/admin/`. The package name `rifapp` was kept from the raffle era because the WSGI/ASGI module path (`rifapp.wsgi`) may be referenced by the hosting config.
- `points/` — the only app (was `raffle/` before the points rewrite). `models.py`, `views.py`, `forms.py`, `admin.py`, `urls.py`, `templates/`, `migrations/`, `tests.py`, `management/commands/sync_prizes.py`.
- `static/` — flat asset dir served via `STATICFILES_DIRS` (`styles.css`, `snowstorm.js`, `manifest.json`, `icons/`, `foto.png`).
- `db.sqlite3` — local DB, gitignored.

## Commands

No `requirements.txt`; `.venv/` is the only dependency source (Django 6.1.3, Pillow, sqlparse — Pillow is required by `Prize.image`).

```bash
.venv/bin/python manage.py runserver
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py makemigrations points
.venv/bin/python manage.py sync_prizes      # ajusta los premios al top N configurado
.venv/bin/python manage.py test          # 33 tests in points/tests.py
.venv/bin/python manage.py check
```

There is no CI, no linter, no pytest config, and no `.github/` directory.

## Model semantics

- `Participant` — a player. `Participant.total_points` is a **property** that sums its `PointEntry` rows; list views instead annotate `points=Sum('point_entries__points')`. Do **not** name an annotation `total_points`: it collides with the property and Django raises `AttributeError: property 'total_points' … has no setter`.
- `PointEntry` — one row per annotation of played time. `points` is the number of hours (1–24), `note` is optional. Totals are always `Sum('point_entries__points')`.
- `Prize` — one row per top-N position (`position` 1..N, unique). Holds the configured prize (name/description/image), the assigned `winner` and the `claimed` flag. Staff configure them at `/premios/<position>/editar/` (that view creates the row on first visit).
- `Prize.winner` is `SET_NULL`: deleting a participant keeps the prize but clears its winner.

## Number of prizes (top N) — configurable

The number of prizes is **not** hardcoded. It comes from `PRIZE_SLOTS` in `rifapp/settings.py` (default `5`), read through `points.models.prize_slot_count()`. Every view, template and the admin follow it, so raising or lowering it is a one-line change:

```python
# rifapp/settings.py
PRIZE_SLOTS = 3   # or 10, etc.
```

Then sync the database:

```bash
.venv/bin/python manage.py sync_prizes                # creates the missing slots
.venv/bin/python manage.py sync_prizes --delete-extra # also removes slots outside the top N
```

- **Increasing** it: `sync_prizes` creates the new slots with a placeholder name so they can be configured right away. Without running it the extra slots still show on `/premios/` as "Premio por anunciar" and can be configured via `/premios/<position>/editar/`.
- **Decreasing** it: prizes whose position is now out of range are **kept** in the database (nothing is deleted by accident); `sync_prizes` reports them and `--delete-extra` removes them. The public pages always show only the positions 1..N.
- `Prize.position` is validated against the configured range (`validate_prize_position`), so the admin refuses positions outside the top N.
- The tests read the same setting, so they pass with any number of prizes.


## Hard-coded dates — these gate all behavior

`points/views.py` defines module-level `START_DATE = date(2026, 11, 1)`, `END_DATE = date(2026, 12, 24)` and `AWARD_DATE = date(2026, 12, 25)` (the Navid 2026 cycle).

- `period_is_open()` is true only inside `START_DATE..END_DATE`; `add_points` **rejects** new entries outside that window (deleting an erroneous entry still works).
- `days_until_award()` drives the countdown shown on the home and prizes pages; `is_award_day` highlights December 25.
- These constants are plain module attributes, not settings — patch them in tests (`unittest.mock.patch('points.views.timezone.localdate', ...)`).

## Ranking rules

- `get_ranking()` returns participants **with at least one point**, ordered by `-points, name`.
- `get_ranked_list()` resolves ties with standard competition ranking (1, 2, 2, 4) and returns `(rank, participant)` tuples.
- Ranking is always live: it is computed from the point entries, never persisted.

## Auth model

Two different kinds of people are involved; do not mix them up:

- **`User`** — an operator of the system (staff or employee). They log in at `/login/` and enter data.
- **`Participant`** — a *player* who accumulates points. They never log in; they are just rows in the ranking.

- **Any authenticated user** (`login_required`) can: add participants (`add_participant`), annotate points (`add_points`) and delete a wrong entry (`delete_point_entry`). The data-entry views require a session, not staff rights.
- **Staff only** (`staff_member_required`) can: configure a prize (`edit_prize`), assign the top N (`assign_top_prizes`) and mark a prize as claimed (`claim_prize`). A non-staff user hitting these gets redirected to the Django admin login.
- There is **no public sign-up**: the staff create the operator accounts from `/admin/`. `LOGIN_URL`, `LOGIN_REDIRECT_URL` and `LOGOUT_REDIRECT_URL` point at the app's own login, not the admin one.
- Logout is a **POST form** (`LogoutView` in Django 6.1 only accepts POST); the nav shows the logged-in username and a "Salir" button.
- The nav links for data entry appear for `user.is_authenticated`; the prize administration link only for `user.is_staff`.
- Every state-changing action is a **POST with CSRF** (`delete_point_entry`, `assign_top_prizes`, `claim_prize`, logout). The raffle-era code mutated state over a plain GET link; that bug is gone.

## Migration / version notes

- The app was renamed `raffle` → `points`. `points/migrations/0002_legacy_cleanup.py` copies the participants of the old `raffle_participant` table into `points_participant` and then drops `raffle_raffle`, `raffle_rafflenumber`, `raffle_dailywinner` and `raffle_participant` (plus the stale `django_migrations` rows for the old app). It is safe on a database that never had the raffle tables.
- `0003_...` only changes field `verbose_name`s (Spanish labels) — no schema change.
- Migrations were generated by Django 5.2.7 / 6.1.3; `manage.py check` passes clean.

## Conventions

- UI strings, comments, docstrings, and template content are in **Spanish**; code identifiers are English. Match this in new code.
- Templates extend `points/templates/layout.html` (Pico CSS via CDN, Christmas fonts, snow effect from `static/snowstorm.js`). Keep the layout's `{% block content %}` / `{% block title %}` structure.
- `.prettierignore` contains `*.html` — HTML templates are **not** prettier-formatted. No prettier config file exists in the repo.
- Frontend effects live in `static/` (plain CSS/JS, no build step). There is no bundler; edit `static/` files directly. `static/lights.css` was removed as dead code (the layout uses the `.christmas-lights` rules in `styles.css`).
- Christmas theme is mandatory: keep the lights, the snow, the festive fonts and the emoji in headings.
