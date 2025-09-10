FROM alpine:3.20

ARG THREEPROXY_VERSION=0.9.5

# Add build tools (make, git) and runtime deps
RUN apk add --no-cache ca-certificates curl tar gettext supervisor python3 py3-psycopg2 openssl \
    supervisor python3 py3-pip gcc musl-dev python3-dev libpq-dev openssl make git

WORKDIR /tmp
# Build and install 3proxy from git tag (tarballs can intermittently 404 via codeload)
RUN git clone --depth 1 --branch ${THREEPROXY_VERSION} https://github.com/3proxy/3proxy.git /tmp/3proxy-src \
 && cd /tmp/3proxy-src \
 && make -f Makefile.Linux \
 && make -f Makefile.Linux install \
 && mkdir -p /usr/local/3proxy/lib \
 && cp -f ./bin/SSLPlugin.ld.so /usr/local/3proxy/lib/ || true \
 && rm -rf /tmp/*

WORKDIR /app

COPY 3proxy/3proxy.cfg.tpl /assets/3proxy.cfg.tpl
COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh
COPY etc/supervisor/supervisord.conf /etc/supervisor/supervisord.conf
COPY ingester/log_ingester.py /app/ingester/log_ingester.py

EXPOSE 3128 1080 8443

ENV LISTEN_HOST=0.0.0.0 HTTP_PORT=3128 SOCKS_PORT=1080 ENABLE_HTTPS_PROXY=false HTTPS_PORT=8443
ENV AUTH_USER=user1 AUTH_PASS=pass1
ENV UPSTREAM_TYPE=socks5 UPSTREAM_HOST=127.0.0.1 UPSTREAM_PORT=1080 UPSTREAM_USER= UPSTREAM_PASS=
ENV PG_HOST=db PG_PORT=5432 PG_DB=proxydb PG_USER=proxy PG_PASSWORD=secret PG_SSLMODE=disable
ENV INGEST_BATCH_SIZE=200 INGEST_FLUSH_INTERVAL=1.0 INGEST_MAX_T_LEN=4096

ENTRYPOINT ["/bin/sh","/entrypoint.sh"]
