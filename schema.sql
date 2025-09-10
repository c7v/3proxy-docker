-- Схема БД для журналирования трафика 3proxy
-- Дата/время в формате TIMESTAMP без часового пояса (UTC). Инжестер конвертирует в UTC.

CREATE TABLE IF NOT EXISTS proxy_sessions (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMP NOT NULL,                  -- время события (UTC)
    service TEXT NOT NULL,                  -- тип сервиса: proxy/socks/...
    username TEXT,                          -- логин клиента (если был)
    client_ip INET NOT NULL,                -- адрес клиента
    client_port INTEGER NOT NULL,
    server_ip INET,                         -- адрес удалённого сервера (как видит 3proxy)
    server_port INTEGER,
    bytes_in BIGINT NOT NULL DEFAULT 0,     -- от клиента к серверу
    bytes_out BIGINT NOT NULL DEFAULT 0,    -- от сервера к клиенту
    hit INTEGER,                            -- код результата (%h)
    extra_text TEXT                         -- текстовая часть (%T): URL/метод/host/SNI и т.п.
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_proxy_sessions_ts ON proxy_sessions (ts);
CREATE INDEX IF NOT EXISTS idx_proxy_sessions_client_ip ON proxy_sessions (client_ip);
CREATE INDEX IF NOT EXISTS idx_proxy_sessions_service ON proxy_sessions (service);
CREATE INDEX IF NOT EXISTS idx_proxy_sessions_username ON proxy_sessions (username);
