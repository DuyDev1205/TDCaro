#!/bin/sh
# Cap nhat & chay lai server tren VPS:  ssh vlxd 'sh ~/_gitclone/tdcaro/server/deploy.sh'
set -e
cd "$(dirname "$0")/.."
git pull --ff-only
cd server
npm ci --omit=dev --no-audit --no-fund
cp tdcaro.service /etc/systemd/system/tdcaro.service
systemctl daemon-reload
systemctl enable --now tdcaro.service
systemctl restart tdcaro.service
sleep 1
systemctl --no-pager --lines=3 status tdcaro.service | head -5
curl -s http://127.0.0.1:8388/ && echo
