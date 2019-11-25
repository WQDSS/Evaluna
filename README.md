# Evaluna [![Build Status](https://travis-ci.com/WQDSS/Evaluna.svg?branch=master)](https://travis-ci.com/WQDSS/Evaluna)
This project suplies a basic DSS infrastructure that can be expanded
for water quality based on CE-QUAL-W2 model (wqdss)


## Using Kubernetes
The DSS is implemented as a set of services that communicate and scale automatically. In order to be independent of a specific service provider, these containerized services are packaged via a Helm chart, that can easily be customized and installed on any kubernetes cluster.

If you're familiar with kubernetes and helm, feel free to skip to the [installation section](#install-using-helm).

Otherwise, see below for links and instructions on how to create your own kubernetes cluster (either [locally](#using-minikube)) or [remotely](#using-google-cloud)

### Installing helm    
The simplest way to install helm is to download the single executable from the [releases page](https://github.com/helm/helm/releases), there are no other pre-requistes, but having a working [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/) is highly recommended

For further details, you can follow the instructions here: https://v3.helm.sh/docs/intro/quickstart/#install-helm

_Note: Currently, the helm chart is tested with helm3, please use that version_

### Using Minikube

Minikube is a tool that allows you to create a single-node kubernetes cluster inside a VM on your local computer. It provides all the facilities of a cloud-based kubernetes cluster, but is available locally to simplify the development cycle.

#### Installing Minikube
See the instructions from the [minikube project]([http://](https://minikube.sigs.k8s.io/docs/start/)) on how to install minikube on your computer.

Assuming that you've got all of the pre-requisites, installing minikube is very straight-forward.

You can then create a minkube environment using the CLI:
```bash
minikube start minikube start --kubernetes-version=v1.16.0  --addons ingress --addons metrics-server
```

The ingress and metrics server addons are selected to allow testing of the ingress definition, and automatic horizontal scaling

### Using Google Cloud
TBD - need to add details and examples here

## Install using helm
The project includes a helm chart that is configured to use the released docker images from the master branch. If you would just like to deploy that version, you can simply use the command:

```bash
helm install wqdss dss/chart/wqdss/ --namespace wqdss
```
This will install the application into the namespaces named ```wqdss``` using the default configuration.


### Automatic Horizontal scaling
In order to support automatic scaling, the DSS application provides a Horizontal Pod Autoscaler (HPA) for the pods which run the model. The min/max number of pods can be specified in the YAML file. The defaults are between 1-5 pods.
Each pod will run as many workers as it has cores to use, effectively trying to utilize all of the available CPU cores.

In order for the HPA to work correctly, the metrics-server monitoring tool must be installed in the Kubernetes cluster.

If you're using a local installation (not minikube or cloud versions), you may need to follow the instructions below to install metrics-server
1. helm pull stable/metrics-server
2. Specify the value for args: --kubelet-insecure-tls
3. Install the helm chart using helm install

Once you have the metrics-server functionality enabled in the cluster, you can install the helm chart with the ```hpa.enabled=true ``` flag to enable automatic horizontal scaling:
```bash
helm install wqdss dss/chart/wqdss/ --namespace wqdss --set hpa.enabled=true 
```

If you choose to have different node types for workers and for the front/backend services (recommended for production, but not for development), please use the following command:

```bash
helm install wqdss dss/chart/wqdss/ --namespace wqdss --set hpa.enabled=true --set affinity.enabled=true
```

In this case please make sure that you label your nodes accordingly:
* ```wqdss-node-type=worker``` label should be used for worker nodes
* ```wqdss-node-type=default``` label should be used for all other nodes.

The only nodes that should be scaled by the cluster autoscaler should be pods from the worker nodepool.

Please review the ```hpa``` section in  ```values.yaml``` file, as there are additional options that can be used to tune the automatic scaling.



## Developing and Contributing
The project is completely open-sourced. Any comments, bug-fixes, and enhancements are more than welcome.

Since the DSS is designed to be deployed on a remote kubernetes cluster, during development the docker images that are created get pushed to dockerhub. In order for this to function correctly, you must have a dockerhub account, or change the script to pusht he images to whatever docker-registry you're using.

In order to ease the development process, please see the following script:
```
dss/scripts/build_and_run_tests.sh
```

This script will create the docker images for the application, as well as an image that is used to drive the automated tests for this package.

### CI and testing
The CI process for this project is provide via Travis CI. After each commit on any branchea sanity test is executed to confirm that no existing behavior is inadvertently broken.
