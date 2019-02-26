#! /bin/bash -e
docker build --rm -f "Dockerfile" -t waterqualitydss-test:latest --target test .
docker build --rm -f "Dockerfile" -t waterqualitydss:latest .

docker-compose -f dss/test/docker-compose.yml up --abort-on-container-exit