#! /bin/bash -e

CURRENT_COMMIT=$(git rev-parse --short HEAD)
docker build --rm -f "Dockerfile" -t waterqualitydss:latest -t "booooh/waterqualitydss:$CURRENT_COMMIT" .
docker push "booooh/waterqualitydss:$CURRENT_COMMIT"

