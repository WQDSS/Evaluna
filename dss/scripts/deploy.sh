#! /bin/bash -ex

TAG=$1

echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
docker push "$DOCKER_USERNAME/waterqualitydss:$TAG"
docker push "$DOCKER_USERNAME/waterqualitydss-test:$TAG"