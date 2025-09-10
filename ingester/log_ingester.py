import os, sys, time
from datetime import datetime, timezone
import re
import psycopg2
from psycopg2.extras import execute_values

FIFO_PATH = "/var/log/3proxy/pipe"

PG_HOST = os.getenv("PG_HOST", "db")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "proxydb")
PG_USER = os.getenv("PG_USER", "proxy")
PG_PASSWORD = os.getenv("PG_PASSWORD", "secret")
PG_SSLMODE = os.getenv("PG_SSLMODE", "disable")

BATCH_SIZE = int(os.getenv("INGEST_BATCH_SIZE", "200"))
FLUSH_INTERVAL = float(os.getenv("INGEST_FLUSH_INTERVAL", "1.0"))
MAX_T_LEN = int(os.getenv("INGEST_MAX_T_LEN", "4096"))

conn = None

def connect():
    global conn
    while True:
        try:
            conn = psycopg2.connect(
                host=PG_HOST, port=PG_PORT, dbname=PG_DB,
                user=PG_USER, password=PG_PASSWORD, sslmode=PG_SSLMODE
            )
            conn.autocommit = False
            print("[ingester] connected to PostgreSQL", flush=True)
            return
        except Exception as e:
            print(f"[ingester] PG connect failed: {e}", file=sys.stderr, flush=True)
            time.sleep(2)

def ensure_fifo():
    if not os.path.exists(FIFO_PATH):
        os.mkfifo(FIFO_PATH)

def parse_ts_utc(ts_str: str):
    # Пример: 2025-09-10T14:22:33+0300  -> переводим в UTC и делаем naive TIMESTAMP
    # Быть устойчивыми к 2-значному году ("25-09-10T...")
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(ts_str, fmt)
            # Если год 2-значный, datetime сам приведёт к 19xx/20xx согласно правилам;
            # приводим к UTC и убираем tzinfo
            dt_utc = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt_utc
        except Exception:
            continue
    # Heuristic: 3proxy may output 'y-' or 'Y-' instead of a year; try to fix by using current UTC year
    m = re.match(r"^[yY]-(\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{4})$", ts_str)
    if m:
        fixed = f"{datetime.utcnow().year}-{m.group(1)}"
        try:
            dt = datetime.strptime(fixed, "%Y-%m-%dT%H:%M:%S%z")
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            pass
    print(f"[ingester] ts_fail: {ts_str}", flush=True)
    return None

def parse_line(line: str):
    # 3proxy выводит символы \t буквально, поэтому превращаем их в реальные табы
    line = line.rstrip("\n").replace("\\t", "\t")
    parts = line.split("\t")
    if len(parts) < 11:
        try:
            preview = line.strip().replace("\t", "\\t")[:300]
            print(f"[ingester] parse_drop: too_few_fields len={len(parts)} line={preview}", flush=True)
        except Exception:
            pass
        return None
    ts = parse_ts_utc(parts[0])
    if ts is None:
        try:
            print(f"[ingester] parse_drop: ts_none raw_ts={parts[0]}", flush=True)
        except Exception:
            pass
        return None
    service = parts[1] or None
    username = parts[2] or None
    client_ip = parts[3] or "0.0.0.0"
    try:
        client_port = int(parts[4])
    except:
        client_port = 0
    server_ip = parts[5] or None
    try:
        server_port = int(parts[6])
    except:
        server_port = None
    try:
        bytes_in = int(parts[7])
    except:
        bytes_in = 0
    try:
        bytes_out = int(parts[8])
    except:
        bytes_out = 0
    try:
        hit = int(parts[9])
    except:
        hit = None
    extra = parts[10]
    if extra.startswith('\"') and extra.endswith('\"'):
        extra = extra[1:-1]
    if len(extra) > MAX_T_LEN:
        extra = extra[:MAX_T_LEN]
    return (ts, service, username, client_ip, client_port, server_ip, server_port, bytes_in, bytes_out, hit, extra)

def main():
    ensure_fifo()
    connect()
    cur = conn.cursor()
    batch = []
    last_flush = time.time()
    dropped = 0

    while True:
        try:
            with open(FIFO_PATH, "r") as f:
                for raw in f:
                    rec = parse_line(raw)
                    if rec is None:
                        dropped += 1
                        if dropped <= 20 or dropped % 100 == 0:
                            preview = raw.strip().replace("\t", "\\t")[:300]
                            print(f"[ingester] dropped[{dropped}]: {preview}", flush=True)
                        continue
                    batch.append(rec)
                    now = time.time()
                    if len(batch) >= BATCH_SIZE or (now - last_flush) >= FLUSH_INTERVAL:
                        execute_values(cur,
                            """INSERT INTO proxy_sessions
                            (ts, service, username, client_ip, client_port, server_ip, server_port, bytes_in, bytes_out, hit, extra_text)
                            VALUES %s""",
                            batch
                        )
                        conn.commit()
                        print(f"[ingester] inserted {len(batch)} rows", flush=True)
                        batch.clear()
                        last_flush = now
        except psycopg2.Error as e:
            print(f"[ingester] PG error: {e}", file=sys.stderr, flush=True)
            try: conn.rollback()
            except: pass
            time.sleep(1)
            connect()
            cur = conn.cursor()
        except Exception as e:
            print(f"[ingester] error: {e}", file=sys.stderr, flush=True)
            time.sleep(0.5)

if __name__ == "__main__":
    main()
