#! /bin/bash -ex

TAG=$1

echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin

docker_username=${DOCKER_USERNAME_FOR_REPO:-evaluna}
docker push "${docker_username}/waterqualitydss:$TAG"
docker push "${docker_username}/waterqualitydss-test:$TAG"