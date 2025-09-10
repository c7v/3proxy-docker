#!/bin/sh
set -eu

: "${LISTEN_HOST:=0.0.0.0}"
: "${HTTP_PORT:=3128}"
: "${SOCKS_PORT:=1080}"
: "${ENABLE_HTTPS_PROXY:=false}"
: "${HTTPS_PORT:=8443}"

: "${AUTH_USER:=user1}"
: "${AUTH_PASS:=pass1}"

: "${UPSTREAM_TYPE:=socks5}"
: "${UPSTREAM_HOST:=127.0.0.1}"
: "${UPSTREAM_PORT:=1080}"
: "${UPSTREAM_USER:=}"
: "${UPSTREAM_PASS:=}"

mkdir -p /usr/local/3proxy/conf /var/log/3proxy /run/3proxy

# envsubst из пакета gettext
envsubst < /assets/3proxy.cfg.tpl > /usr/local/3proxy/conf/3proxy.cfg

case "$(printf "%s" "${ENABLE_HTTPS_PROXY}" | tr '[:upper:]' '[:lower:]')" in
  true|1|yes)
    : "${TLS_CERT_PATH:?TLS_CERT_PATH is required when ENABLE_HTTPS_PROXY=true}"
    : "${TLS_KEY_PATH:?TLS_KEY_PATH is required when ENABLE_HTTPS_PROXY=true}"
    cat >> /usr/local/3proxy/conf/3proxy.cfg <<EOF

plugin /usr/local/3proxy/lib/SSLPlugin.ld.so
ssl_cert ${TLS_CERT_PATH}
ssl_key ${TLS_KEY_PATH}
tcppm -st -i${LISTEN_HOST} -p${HTTPS_PORT} 127.0.0.1 ${HTTP_PORT}
EOF
  ;;
esac

# FIFO для логов
if [ ! -p /var/log/3proxy/pipe ]; then
  mkfifo /var/log/3proxy/pipe
fi

exec /usr/bin/supervisord -c /etc/supervisor/supervisord.conf
