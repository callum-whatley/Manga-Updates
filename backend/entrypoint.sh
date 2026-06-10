#!/bin/sh
set -e
flask db upgrade
exec gunicorn --workers 1 --bind 0.0.0.0:5001 --timeout 120 run:app
