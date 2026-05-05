#!/bin/sh
set -e
# Flask bindet in server.py an 127.0.0.1 — ohne Code-Änderung ist der Dienst
# im Container nicht über die Bridge erreichbar. socat published BACKEND_EXPOSE_PORT
# auf allen Interfaces und leitet zu 127.0.0.1:BACKEND_INTERNAL_PORT weiter.
INTERNAL="${BACKEND_INTERNAL_PORT:-5002}"
EXTERNAL="${BACKEND_EXPOSE_PORT:-5001}"
export BACKEND_PORT="$INTERNAL"
socat "TCP-LISTEN:${EXTERNAL},fork,reuseaddr,bind=0.0.0.0" "TCP:127.0.0.1:${INTERNAL}" &
exec gosu appuser python server.py
