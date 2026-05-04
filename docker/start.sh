#!/usr/bin/env bash

docker compose \
  -f docker-compose.yml \
  -f docker-compose-opendataloader.yml \
  -f docker-compose-mineru.yml \
  up -d
