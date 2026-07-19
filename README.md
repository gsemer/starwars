# SWAPI Explorer API

A RESTful API that imports Star Wars characters, films, and starships from
[SWAPI](https://swapi.dev/), stores them in PostgreSQL, and lets clients
browse (paginated) and vote for their favourites.

Built with **FastAPI**, **SQLAlchemy 2.0 (async)**, **PostgreSQL**, **Redis**,
**HTTPX**, **asyncio**, and a **Domain-Driven Design** structure.

---

## Table of contents

- [Architecture](#architecture)
- [Project structure](#project-structure)
- [Environment setup](#environment-setup)
- [Configuration](#configuration)
- [Running with Docker (Postgres + Redis)](#running-with-docker-postgres--redis)
- [Database migrations](#database-migrations)
- [Running the application](#running-the-application)
- [Running tests](#running-tests)
- [Coverage report](#coverage-report)
- [API reference](#api-reference)

---

## Architecture

### Layers

~~~
app/
├── domain/          # Entities, all interfaces (repos, services, SWAPI client,
│                     lock provider), pagination, import result, exceptions. No I/O.
├── services/         # Concrete service implementations of the domain interfaces.
├── infrastructure/   # SQLAlchemy repositories, HTTPX SWAPI client, Redis lock, DB session.
└── api/               # FastAPI routers, Pydantic schemas, DI wiring.
~~~

Every abstract contract lives in `domain/interfaces/` — the repository
interfaces, the service interfaces, the `SWAPIClient` interface, and the
`LockProvider` interface. Concrete implementations (`app/services/`,
`app/infrastructure/`) depend on and implement these, never the other way
around.

### Services are singletons

Each service (`CharacterServiceImpl`, `FilmServiceImpl`,
`StarshipServiceImpl`) is created **once**, at startup, by `Container`
(`app/core/container.py`) and stored on `app.state`. The FastAPI
dependencies just return the existing instance:

~~~python
def get_character_service(request: Request) -> CharacterService:
    return request.app.state.character_service
~~~

No service or repository is rebuilt per request. Each service holds a
**session factory** (not a session), so a single long-lived instance opens
and closes its own session per call and can safely serve concurrent
requests.

### Import: single-flight with Redis

`import_characters` / `import_films` / `import_starships` coordinate across
all workers/processes using a Redis-backed lock plus a cached result:

1. **Cache check first** — if a recent import result is already cached in
   Redis, it's returned immediately (no SWAPI traffic, no DB writes).
2. **Acquire the lock** (`SET key token NX PX ttl`) — the winner streams
   records from SWAPI (async generator, page by page), upserts them in
   batches, publishes the serialized result to Redis, then releases the
   lock.
3. **Contended callers wait** — if the lock is held, the caller polls for
   the cached result (up to a timeout). If the result appears, it's
   returned; if the wait times out, an `ExternalServiceError` (HTTP 502)
   is raised.

This means N concurrent import requests result in a single real import,
and everyone else reads the shared result — instead of duplicating the
work.

### Idempotent, concurrency-safe writes

Each SWAPI resource exposes a `url` (e.g. `.../people/1/`); the trailing
integer is stored as `swapi_id` — a separate, unique, indexed column from
the internal UUID primary key. `bulk_upsert()` uses PostgreSQL's
`INSERT ... ON CONFLICT (swapi_id) DO UPDATE`, so re-running an import
never creates duplicate rows.

### Many-to-many relationships

`characters` ↔ `films` and `starships` ↔ `films` are association tables
(`character_films`, `starship_films`) with a unique constraint on the FK
pair. Linking uses `INSERT ... ON CONFLICT DO NOTHING`, so re-linking is a
safe no-op. **Import films before characters/starships** so film
associations can resolve.

### Concurrency control on outbound SWAPI calls

The `HTTPXSWAPIClient` shares an `asyncio.Semaphore` (size configured by
`MAX_CONCURRENCY`) to bound how many requests hit SWAPI at once from a
single worker process, and retries transient failures (429/5xx, transport
errors) with exponential backoff.

### Error handling

Domain exceptions are translated to HTTP responses in
`app/api/error_handlers.py`, all sharing a consistent shape
`{"detail": "...", "error_code": "..."}`:

| Exception | HTTP status | `error_code` |
|---|---|---|
| `EntityNotFoundError` | 404 | `ENTITY_NOT_FOUND` |
| `ExternalServiceError` | 502 | `EXTERNAL_SERVICE_ERROR` |
| `DomainError` (other) | 400 | `DOMAIN_ERROR` |
| unhandled `Exception` | 500 | `INTERNAL_SERVER_ERROR` |

---

## Project structure

No `__init__.py` files — the codebase relies on Python's native namespace
packages; every import is an explicit submodule import.

~~~
app/
├── api/
│   ├── endpoints/          # characters.py, films.py, starships.py
│   ├── schemas/             # Pydantic request/response models
│   ├── dependencies.py      # returns the singleton services from app.state
│   ├── error_handlers.py
│   └── router.py
├── core/                     # config, container (DI wiring), logging
├── domain/
│   ├── entities/               # Character, Film, Starship
│   ├── interfaces/              # every abstract contract in the app
│   ├── pagination.py            # PaginationParams + PageResult
│   ├── import_result.py
│   └── exceptions.py
├── services/                    # CharacterServiceImpl, FilmServiceImpl, StarshipServiceImpl
├── infrastructure/
│   ├── database/                 # SQLAlchemy models, engine/session
│   ├── repositories/              # SQLAlchemy repository implementations
│   ├── cache/redis_lock_provider.py
│   └── external/swapi_client.py   # HTTPXSWAPIClient
└── main.py

alembic/          # DB migrations
tests/            # unittest-based test suite
docker-compose.yml
~~~

---

## Environment setup

**Prerequisites:** Python 3.12+, PostgreSQL 16+, Redis 7+ (Docker Compose
provides Postgres and Redis — see below).

~~~bash
git clone https://github.com/gsemer/starwars.git
cd starwars

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt        # to run the app
pip install -r requirements-dev.txt    # to also run the tests
~~~

---

## Configuration

Copy `.env.example` to `.env` and adjust as needed:

~~~bash
cp .env.example .env
~~~

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | Async SQLAlchemy connection string (asyncpg) | `postgresql+asyncpg://swapi:swapi@localhost:5433/swapi` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6381/0` |
| `IMPORT_LOCK_TTL_SECONDS` | Import lock auto-expiry (deadlock protection) | `300` |
| `SWAPI_BASE_URL` | Base URL for SWAPI | `https://swapi.dev/api` |
| `SWAPI_MAX_RETRIES` / `SWAPI_BACKOFF_BASE_SECONDS` | Retry/backoff tuning | `3` / `0.5` |
| `IMPORT_BATCH_SIZE` | Records per upsert batch during import | `50` |
| `MAX_CONCURRENCY` | Max concurrent outbound SWAPI requests per worker | `1` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `API_V1_PREFIX` | URL prefix for v1 routes | `/api/v1` |

> The defaults in `app/core/config.py` assume the Docker Compose ports
> below (Postgres on **5433**, Redis on **6381**). If you run Postgres/Redis
> some other way, update `DATABASE_URL` / `REDIS_URL` accordingly.

---

## Running with Docker (Postgres + Redis)

The included `docker-compose.yml` starts both dependencies:

~~~bash
docker compose up -d
docker compose ps        # confirm both are healthy
~~~

- Postgres → `localhost:5433` (user/password/db all `swapi`)
- Redis → `localhost:6381`

Stop them with `docker compose down` (add `-v` to also wipe the volumes).

---

## Database migrations

~~~bash
alembic upgrade head                                   # apply all migrations
alembic revision --autogenerate -m "describe change"    # after changing models
~~~

Creates `characters`, `films`, `starships` (UUID PK, unique+indexed
`swapi_id`, `votes` counter) and the `character_films` / `starship_films`
association tables.

---

## Running the application

~~~bash
uvicorn app.main:app --reload
~~~

- API base: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`
- OpenAPI schema: `http://localhost:8000/openapi.json`

---

## Running tests

The test suite uses Python's built-in **`unittest`** and
**`unittest.mock`** (with `AsyncMock`). Every external dependency (the DB
session, the SWAPI HTTP client, the Redis lock) is mocked or faked, so the
tests run with no PostgreSQL, no Redis, and no network access.

~~~bash
python -m unittest discover -s tests -p "test_*.py"
~~~

Verbose:

~~~bash
python -m unittest discover -s tests -p "test_*.py" -v
~~~

---

## Coverage report

Coverage is measured with [`coverage.py`](https://coverage.readthedocs.io/):

~~~bash
# run the tests under coverage
python -m coverage run --source=app -m unittest discover -s tests -p "test_*.py"

# terminal summary with missing line numbers
python -m coverage report -m

# browsable HTML report -> open htmlcov/index.html
python -m coverage html
~~~

---

## API reference

Each resource (`characters`, `films`, `starships`) exposes exactly three
endpoints — **import**, **list (paginated)**, and **vote**. List endpoints
perform pagination only.

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/characters/import` | Fetch characters from SWAPI and upsert them |
| `GET` | `/api/v1/characters?page=&page_size=` | List characters (paginated) |
| `POST` | `/api/v1/characters/{id}/vote` | Vote for a character |
| `POST` | `/api/v1/films/import` | Fetch films from SWAPI and upsert them |
| `GET` | `/api/v1/films?page=&page_size=` | List films (paginated) |
| `POST` | `/api/v1/films/{id}/vote` | Vote for a film |
| `POST` | `/api/v1/starships/import` | Fetch starships from SWAPI and upsert them |
| `GET` | `/api/v1/starships?page=&page_size=` | List starships (paginated) |
| `POST` | `/api/v1/starships/{id}/vote` | Vote for a starship |

Import films first so film associations resolve:

~~~bash
curl -X POST http://localhost:8000/api/v1/films/import
curl -X POST http://localhost:8000/api/v1/characters/import
curl -X POST http://localhost:8000/api/v1/starships/import

curl "http://localhost:8000/api/v1/characters?page=1&page_size=20"
curl -X POST http://localhost:8000/api/v1/characters/<uuid>/vote
~~~