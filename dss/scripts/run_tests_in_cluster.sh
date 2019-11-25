#! /bin/bash -e
# create a namespace for the test
tag=$1
test_ns=wqdss-test-${tag}
kubectl create ns ${test_ns}

# deploy the helm chart with the testing flag set
helm install wqdss dss/chart/wqdss/ --namespace ${test_ns} --set test.enabled=true --wait

# hack for bash in windows
if [ -n "$MSYSTEM" ] ; then
    MSYS2_ARG_CONV_EXCL="/test"
    echo "setting an exception for /test renaming"
    export MSYS2_ARG_CONV_EXCL
fi

ret=0
kubectl --namespace ${test_ns} exec -it wqdss-test /test/run_tests.sh /test/ || ret=$?
echo "Return value for test was $ret"

# if test was successfull - clean up the helm release and k8s namespace
if [ $ret -eq 0 ]; then
    echo "Test completed successfully, deleting namespace and chart"
    helm delete --namespace ${test_ns} wqdss
    kubectl delete ns "${test_ns}"
fi
echo "going to exit with ${ret}"
exit ${ret}