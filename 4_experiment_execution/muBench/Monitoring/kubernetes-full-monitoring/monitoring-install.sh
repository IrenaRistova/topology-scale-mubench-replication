# Secure .kube
chmod go-r -R ~/.kube/

# Prometherus
kubectl create namespace monitoring
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install prometheus prometheus-community/kube-prometheus-stack -n monitoring

# Prometheus (30000) and Grafana (30001) NodePort Services
kubectl apply -f prometheus-nodeport.yaml -n monitoring
kubectl apply -f grafana-nodeport.yaml -n monitoring

# Set system limits for Istio
# Uses minikube ssh to execute commands inside the minikube VM
# Sets three important system limits:
# fs.file-max: Maximum number of file handles that can be opened by the system (1M)
# fs.inotify.max_user_instances: Maximum number of inotify instances per user (1M)
# fs.inotify.max_user_watches: Maximum number of files that can be watched by inotify (1M)
# These are system-level settings that need to be set before Istio can use higher limits
# NOTE: This command is now run from the host in setup.sh
# minikube ssh "sudo sysctl -w fs.file-max=1048576 && sudo sysctl -w fs.inotify.max_user_instances=1048576 && sudo sysctl -w fs.inotify.max_user_watches=1048576"

# Istio
helm repo add istio https://istio-release.storage.googleapis.com/charts
helm repo update
kubectl create namespace istio-system
helm install istio-base istio/base -n istio-system
# Sets container-level ulimit settings:
# soft=1048576: The soft limit (1M) that can be temporarily exceeded
# hard=1048576: The hard limit (1M) that cannot be exceeded
# Sets the security context to run as user/group 1337 (Istio's default)
helm install istiod istio/istiod -n istio-system \
  --set global.proxy.tracer="zipkin" \
  --set global.proxy.containerSecurityContext.ulimits.nofile.soft=1048576 \
  --set global.proxy.containerSecurityContext.ulimits.nofile.hard=1048576 \
  --set global.proxy.containerSecurityContext.runAsUser=1337 \
  --set global.proxy.containerSecurityContext.runAsGroup=1337 \
  --set global.proxy.resources.requests.cpu=10m \
  --set global.proxy.resources.limits.cpu=25m \
  --wait
helm install istio-ingressgateway istio/gateway -n istio-system \
  --set global.proxy.containerSecurityContext.ulimits.nofile.soft=1048576 \
  --set global.proxy.containerSecurityContext.ulimits.nofile.hard=1048576 \
  --set global.proxy.containerSecurityContext.runAsUser=1337 \
  --set global.proxy.containerSecurityContext.runAsGroup=1337 \
  --set global.proxy.resources.requests.cpu=10m \
  --set global.proxy.resources.limits.cpu=25m
kubectl label namespace default istio-injection=enabled

# Istio - Prometeus integration
kubectl apply -f istio-prometheus-operator.yaml

# Jarger
kubectl apply -f jaeger.yaml

# Jaeger NodePort Service (30002)
kubectl apply -f jaeger-nodeport.yaml

#Kiali
helm repo add kiali https://kiali.org/helm-charts
helm repo update
helm install \
  -n istio-system \
  -f kiali-values.yaml \
  kiali-server \
  kiali/kiali-server

#Kiali NodePort Service (30003)
kubectl apply -f kiali-nodeport.yaml

