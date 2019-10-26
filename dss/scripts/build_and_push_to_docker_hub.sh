#! /bin/bash -e

current_commit=$(git rev-parse --short HEAD)
image_tag=${TAG:-$current_commit}
docker build --rm -f "Dockerfile" -t waterqualitydss:latest -t "booooh/waterqualitydss:$image_tag" .
docker push "booooh/waterqualitydss:$image_tag"

