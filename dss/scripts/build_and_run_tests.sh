#! /bin/bash -e

TAG=$(date +%s)
export TAG

# build the docker images, including the test image, and bump the appVersion in the chart
./dss/scripts/build_and_push_to_docker_hub.sh bump

# create a namespace for the test
test_ns=wq2dss-test-${TAG}
kubectl create ns ${test_ns}

# deploy the helm chart with the testing flag set
helm install wq2dss dss/chart/wq2dss/ --namespace ${test_ns} --set test.enabled=true

# wait for everything to come up (no init container and readiness checks in place yet)
# TODO: remove the sleep when waiting for all components will work
sleep 30

# hack for bash in windows
if [ -n "$MSYSTEM" ] ; then
    MSYS2_ARG_CONV_EXCL="/test"
    echo "setting an exception for /test renaming"
    export MSYS2_ARG_CONV_EXCL
fi

ret=0
kubectl --namespace ${test_ns} exec -it wq2dss-test /test/run_tests.sh /test/ || ret=$?
echo "Return value for test was $ret"

# if test was successfull - clean up the helm release and k8s namespace
if [ $ret -eq 0 ]; then
    echo "Test completed successfully, deleting namespace and chart"
    helm delete --namespace ${test_ns} wq2dss
    kubectl delete ns "${test_ns}"
fi
echo "going to exit with ${ret}"
exit ${ret}
