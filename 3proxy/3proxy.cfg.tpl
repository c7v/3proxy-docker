nscache 65536
timeouts 1 5 30 60 180 1800 15 60
stacksize 6000

auth strong
users ${AUTH_USER}:CL:${AUTH_PASS}
flush

# Логи в FIFO
logformat "%y-%m-%dT%H:%M:%S%z\t%E\t%U\t%C\t%c\t%R\t%r\t%I\t%O\t%h\t%T"
log /var/log/3proxy/pipe

# Цепочка к родительскому прокси
allow *
parent 1000 ${UPSTREAM_TYPE} ${UPSTREAM_HOST} ${UPSTREAM_PORT} ${UPSTREAM_USER} ${UPSTREAM_PASS}

# Сервисы для клиентов
allow *
proxy -n -p${HTTP_PORT} -i${LISTEN_HOST}
allow *
socks -n -p${SOCKS_PORT} -i${LISTEN_HOST}

# TLS-вход (добавляется entrypoint-ом при ENABLE_HTTPS_PROXY=true)
