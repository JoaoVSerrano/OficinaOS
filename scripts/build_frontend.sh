#!/bin/sh
# Compila o Angular (CSR) e publica SOMENTE o build atual em backend/static,
# apagando os bundles antigos (main-*.js acumulados).
set -e
cd "$(dirname "$0")/.."
WEB=frontend/oficinaos-web
(cd "$WEB" && { [ -d node_modules ] || npm ci; } && npx ng build)
SRC="$WEB/dist/oficinaos-web/browser"
[ -f "$SRC/index.html" ] || { echo "build sem index.html em $SRC" >&2; exit 1; }
rm -rf backend/static
mkdir -p backend/static
cp -R "$SRC"/. backend/static/
echo "backend/static atualizado: $(ls backend/static | wc -l) arquivos, $(ls backend/static/main-*.js | wc -l) bundle(s) main"
