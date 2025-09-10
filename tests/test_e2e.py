import os
import subprocess
import sys
import time
from typing import Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def run(cmd: str, check: bool = True) -> Tuple[int, str, str]:
    p = subprocess.Popen(cmd, shell=True, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate()
    if check and p.returncode != 0:
        raise RuntimeError(f"Command failed ({p.returncode}): {cmd}\nSTDOUT:\n{out}\nSTDERR:\n{err}")
    return p.returncode, out, err


def wait_for_logs(substr: str, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        code, out, _ = run("docker compose logs --no-log-prefix proxy | tail -n 400", check=False)
        if substr in out:
            return
        time.sleep(1.5)
    raise TimeoutError(f"Did not observe '{substr}' in proxy logs within {timeout}s")


def psql_count_max() -> Tuple[int, str]:
    cmd = (
        "docker exec -i $(docker compose ps -q db) sh -lc "
        "'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc ""SELECT count(*), COALESCE(to_char(max(ts),'YYYY-MM-DD HH24:MI:SS'),'') FROM proxy_sessions;""'"
    )
    _, out, _ = run(cmd)
    out = out.strip()
    # Expected format: "<count>|<max_ts>"
    count_str, _, max_ts = out.partition("|")
    try:
        count = int(count_str.strip())
    except Exception:
        raise AssertionError(f"Unexpected psql output: {out!r}")
    return count, max_ts.strip()


def curl_via_proxy(url: str) -> None:
    cmd = f"curl -sS -o /dev/null -x http://user1:pass1@127.0.0.1:3128 {url}"
    run(cmd)


def ensure_compose_up() -> None:
    run("docker compose up -d --build")
    # Wait 3proxy service running
    wait_for_logs("success: 3proxy entered RUNNING state", timeout=120)
    # Wait ingester connected at least once
    wait_for_logs("[ingester] connected to PostgreSQL", timeout=60)


def compose_down() -> None:
    run("docker compose down -v", check=False)


def test_http_and_https_ingest() -> None:
    try:
        ensure_compose_up()
        # Baseline count
        c0, _ = psql_count_max()

        # HTTP
        curl_via_proxy("http://example.com/")
        time.sleep(2)
        c1, _ = psql_count_max()
        assert c1 >= c0 + 1, f"expected HTTP request to increase rows (before={c0}, after={c1})"

        # HTTPS CONNECT
        curl_via_proxy("https://qso.su/")
        time.sleep(2)
        c2, _ = psql_count_max()
        assert c2 >= c1 + 1, f"expected HTTPS CONNECT to increase rows (before={c1}, after={c2})"

    finally:
        compose_down()

