#! /bin/bash -e

TAG=$(date +%s)
export TAG

# build the docker images, including the test image, and bump the appVersion in the chart
./dss/scripts/build_and_push_to_docker_hub.sh bump

# run the tests in the cluster
./dss/scripts/run_tests_in_cluster.sh $TAG
