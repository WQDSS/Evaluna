#! /bin/bash -e
docker build --rm -f "Dockerfile" --build-arg http_proxy="$http_proxy" --build-arg https_proxy="$https_proxy" -t waterqualitydss-test:latest --target test .
docker build --rm -f "Dockerfile" --build-arg http_proxy="$http_proxy" --build-arg https_proxy="$https_proxy" -t waterqualitydss:latest .

docker-compose -f dss/test/docker-compose.yml up --abort-on-container-exit