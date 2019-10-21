# Evaluna
This project suplies a basic DSS infrastructure that can be expanded
for water quality based on CE-QUAL-W2 model


## Using Kubernetes
In order to support automatic scaling, the DSS application provides a Horizontal Pod Autoscaler (HPA) for the pods which run the model. The min/max number of pods can be specified in the YAML file. The defaults are between 1-5 pods.
Each pod will run as many workers as it has cores to use, effectively trying to utilize all of the available CPU cores.

In order for the HPA to work correctly, the metrics-server monitoring tool must be installed in the Kubernetes cluster.

Below are some notes about installing it

### Using Docker Desktop
First - install the metrics-server
1. helm pull stable/metrics-server
2. Specify the value for args: --kubelet-insecure-tls
3. Install the helm chart using helm install

Now use kubectl apply -f dss/k8s/ to deploy all of the k8s resources.
By default, the main API will be deployed with a NodePort service.
Use ```kubectl get svc wq2dss``` to find which port it is exposed on.

