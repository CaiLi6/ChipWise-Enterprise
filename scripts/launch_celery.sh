#!/bin/bash
set -e
cd /home/mech-mindai/ChipWise-Enterprise
source .venv/bin/activate
set -a
source .env
set +a
export DATABASE_URL="postgresql://chipwise:${PG_PASSWORD}@localhost:5432/chipwise"
mkdir -p logs
CELERY="$(pwd)/.venv/bin/celery"
nohup "$CELERY" -A src.ingestion.tasks worker -Q default,embedding -c 1 -n w1@%h > logs/celery-w1.log 2>&1 &
echo "W1=$!"
nohup "$CELERY" -A src.ingestion.tasks worker -Q heavy -c 1 -n w2@%h > logs/celery-w2.log 2>&1 &
echo "W2=$!"
nohup "$CELERY" -A src.ingestion.tasks worker -Q crawler -c 1 -n w3@%h > logs/celery-w3.log 2>&1 &
echo "W3=$!"
nohup "$CELERY" -A src.ingestion.tasks beat --loglevel=info > logs/celery-beat.log 2>&1 &
echo "BEAT=$!"
sleep 1
echo "done"
