#! /bin/bash -ex

# this gets executed on the master branch, we want to update the docker images that were previously tagged by the latest tag.
# This isn't the best approach, as it can unexpectedly break things for users...  but will use it for now
COMMIT=$1
if [ -n "$2" ] ; then
    TAG=$2
else
    TAG=$(git describe --tags)
fi


echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin

docker_username=${DOCKER_USERNAME_FOR_REPO:-evaluna}

for image in (waterqualitydss waterqualitydss-test) ; do 
    docker push "${docker_username}/${image}:$COMMIT"
    docker tag "${docker_username}/${image}:$COMMIT" "${docker_username}/${image}:$TAG"
    docker push "${docker_username}/${image}:$TAG"
done

