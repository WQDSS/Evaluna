#! /bin/bash -e
docker build --rm -f "Dockerfile" -t waterqualitydss:latest .

docker-compose -f dss/docker-compose.yml up --abort-on-container-exit