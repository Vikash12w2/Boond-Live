#!/usr/bin/env bash
# Assemble the Lambda code for infra/template.yaml: engine/ + backend/boond + Linux wheels for python3.13.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
out="$root/.build/lambda"
rm -rf "$out" && mkdir -p "$out"
cp -r "$root/engine" "$root/backend/boond" "$out/"
rm -rf "$out/engine/tests"
find "$out" -name __pycache__ -prune -exec rm -rf {} +
# http-ece (a pywebpush dependency) ships only as a source package; it is pure Python,
# so build its wheel locally and let the Linux-only install pick it up.
wheels="$root/.build/wheels"
rm -rf "$wheels" && mkdir -p "$wheels"
python3 -m pip wheel --quiet --disable-pip-version-check --no-deps "http-ece>=1.1.0" -w "$wheels"
python3 -m pip install --quiet --disable-pip-version-check -r "$root/backend/requirements.txt" -t "$out" \
  --find-links "$wheels" --platform manylinux2014_x86_64 --implementation cp --python-version 3.13 --only-binary=:all:
echo "packaged $(du -sh "$out" | cut -f1) into $out"
