# 3proxy → upstream proxy с записью трафика в PostgreSQL

Проект поднимает связку из двух контейнеров: 3proxy (с инжестером логов) и PostgreSQL. Он позволяет прозрачно проксировать HTTP/HTTPS/SOCKS5‑трафик через заданный upstream-прокси и параллельно сохранять сессии в базу данных для аудита, аналитики и отладки.

Зачем это нужно
- Централизованный аудит и аналитика трафика без MITM: видны метаданные (метод/URL/host/SNI, байты, клиент/сервер/порты, статус), но не содержимое HTTPS.
- Быстрый старт: всё поднимается одной командой docker compose.
- Минимальная задержка: лог в FIFO и батч‑вставки в БД.

Архитектура
- service proxy: 3proxy + конфиг логов в FIFO `/var/log/3proxy/pipe`.
- ingester: процесс, читающий FIFO, парсит лог-строки, конвертирует время в UTC и батчами пишет в PostgreSQL.
- service db: контейнер PostgreSQL. При первом старте схема автоматически применится из `docker-entrypoint-initdb.d/01_schema.sql`.

Что сохраняется в БД
Таблица `proxy_sessions` (UTC‑время):
- `ts` (TIMESTAMP, UTC), `service`, `username`, `client_ip`, `client_port`, `server_ip`, `server_port`,
- `bytes_in`, `bytes_out`, `hit`, `extra_text` (строка формата `%T`: метод/URL/host/SNI и пр.).

Быстрый старт
1) Настройте `.env` (файл уже в репозитории). Минимум:
- `UPSTREAM_TYPE`, `UPSTREAM_HOST`, `UPSTREAM_PORT` (+ при необходимости `UPSTREAM_USER`, `UPSTREAM_PASS`).
- Локальные порты: `HTTP_PORT`, `SOCKS_PORT` (и `ENABLE_HTTPS_PROXY=true` + `HTTPS_PORT`, если хотите вход по HTTPS к самому прокси).
- Авторизация клиентов на входе: `AUTH_USER`, `AUTH_PASS` (если нужна).
- Параметры PostgreSQL уже заданы по умолчанию, при необходимости измените: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`.

2) Запустите стек:
```bash
docker compose up -d --build
```

3) Подключайтесь к прокси:
- HTTP: `http://<host>:${HTTP_PORT}`
- SOCKS5: `socks5://<host>:${SOCKS_PORT}`
- Вход по HTTPS к самому прокси (опционально): `https://<host>:${HTTPS_PORT}` при `ENABLE_HTTPS_PROXY=true`

Проверка работы (E2E‑тест)
Локально можно прогнать end‑to‑end тест, который делает HTTP и HTTPS CONNECT запросы через прокси и проверяет, что их видно в `proxy_sessions`:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip pytest
pytest -q
```
Ожидаемый результат: `1 passed`.

Полезные команды
```bash
docker compose logs -f proxy
docker compose logs -f db
docker exec -it $(docker compose ps -q db) psql -U ${POSTGRES_USER} -d ${POSTGRES_DB}
```

Резервное копирование БД
```bash
docker exec -it $(docker compose ps -q db) pg_dump -U ${POSTGRES_USER} ${POSTGRES_DB} > dump.sql
```

Переменные окружения (.env)
- Клиентские порты: `LISTEN_HOST`, `HTTP_PORT`, `SOCKS_PORT`, `ENABLE_HTTPS_PROXY`, `HTTPS_PORT`.
- Авторизация клиентов: `AUTH_USER`, `AUTH_PASS`.
- Апстрим (родительский прокси): `UPSTREAM_TYPE` = `socks5` | `connect` | `socks4` | `tls`, `UPSTREAM_HOST`, `UPSTREAM_PORT`, `UPSTREAM_USER`, `UPSTREAM_PASS`.
- PostgreSQL (встроенный сервис): `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`.
- Подключение инжестера к БД: `PG_HOST` (обычно `db`), `PG_PORT`, `PG_DB`, `PG_USER`, `PG_PASSWORD`, `PG_SSLMODE`.
- Инжестер: `INGEST_BATCH_SIZE`, `INGEST_FLUSH_INTERVAL`, `INGEST_MAX_T_LEN`.

Ограничения и заметки
- Для HTTPS содержимое не расшифровывается; видны только параметры CONNECT/SNI/хост и размеры.
- При первом запуске создаётся том `pgdata` и накатывается схема — повторный запуск не перезаписывает данные.

