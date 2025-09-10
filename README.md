# 3proxy → upstream proxy с записью трафика в PostgreSQL (встроенный Postgres)

Готовый стек из двух контейнеров: **proxy** (3proxy + инжестер) и **db** (PostgreSQL).
При первом старте база **автоматически инициализируется** из `docker-entrypoint-initdb.d/01_schema.sql`.
Дата/время сохраняются как **TIMESTAMP (UTC)** — инжестер конвертирует из логов в UTC и записывает _naive_ TIMESTAMP.

## Быстрый старт
1. Скопируйте `.env` и отредактируйте:
   ```bash
   cp .env.example .env
   # укажите UPSTREAM_*, при необходимости AUTH_*, и, если хотите, измените POSTGRES_*
   ```
2. Запуск:
   ```bash
   docker compose up --build -d
   ```
3. Подключайтесь к прокси:
   - HTTP: `http://<host>:${HTTP_PORT}`
   - SOCKS5: `socks5://<host>:${SOCKS_PORT}`
   - (опц.) HTTPS-вход к прокси: `https://<host>:${HTTPS_PORT}` при `ENABLE_HTTPS_PROXY=true`

## Что пишется в БД
Таблица `proxy_sessions` (см. `schema.sql`):
- `ts` — **TIMESTAMP (UTC)**,
- `service`, `username`, `client_ip`, `client_port`, `server_ip`, `server_port`,
- `bytes_in`, `bytes_out`, `hit`, `extra_text` (протокольный текст `%T`: URL/метод/host/SNI и т.д.).

## Как это работает
- 3proxy слушает HTTP и SOCKS5, все запросы идёт через `parent` на ваш upstream-прокси.
- Логирование: `logformat` → **FIFO** `/var/log/3proxy/pipe` (низкая задержка, без диска).
- Инжестер (Python) парсит строки, переводит время в **UTC TIMESTAMP**, делает батч‑вставки в PostgreSQL.
- Схема БД заливается автоматически при _первой_ инициализации тома `pgdata`.

## Переменные окружения (только .env)
- Клиентские порты: `HTTP_PORT`, `SOCKS_PORT`, `ENABLE_HTTPS_PROXY`, `HTTPS_PORT`, `LISTEN_HOST`.
- Авторизация клиентов: `AUTH_USER`, `AUTH_PASS`.
- Апстрим: `UPSTREAM_TYPE` = `socks5` | `connect` | `socks4` | `tls`; плюс `UPSTREAM_HOST`, `UPSTREAM_PORT`, `UPSTREAM_USER`, `UPSTREAM_PASS`.
- PostgreSQL встроенный: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`.
- Подключение приложения к БД: `PG_HOST` (по умолчанию `db`), `PG_PORT`, `PG_DB`, `PG_USER`, `PG_PASSWORD`, `PG_SSLMODE`.
- Инжестер: `INGEST_BATCH_SIZE`, `INGEST_FLUSH_INTERVAL`, `INGEST_MAX_T_LEN`.

## Замечания по производительности
- FIFO + TAB‑лог формат → минимум накладных.
- Батч‑инсерты с коротким интервалом → низкая задержка без нагрузки на БД.
- Нет MITM → максимум скорости. Для HTTPS мы видим только метаданные (CONNECT/SNI/host), содержимое не расшифровывается.

## Резервное копирование БД
Том `pgdata` хранит данные. Дамп:
```bash
docker exec -it $(docker compose ps -q db) pg_dump -U ${POSTGRES_USER} ${POSTGRES_DB} > dump.sql
```

## Полезные команды
```bash
docker compose logs -f proxy
docker compose logs -f db
docker exec -it $(docker compose ps -q db) psql -U ${POSTGRES_USER} -d ${POSTGRES_DB}
```

