import os
from kubernetes import client, config
from kubernetes.client.rest import ApiException


def main():
    # Load kube config (in-cluster)
    try:
        config.load_incluster_config()
    except:
        config.load_kube_config()

    v1 = client.CoreV1Api()

    # Step 0: Get current pod name from env, discover namespace from serviceaccount file
    pod_name = os.getenv("HOSTNAME")
    if not pod_name:
        print("❌ HOSTNAME must be supplied as an environment variable.")
        exit(1)

    try:
        with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r") as f:
            namespace = f.read().strip()
    except Exception as e:
        print(f"❌ Unable to determine namespace: {e}")
        exit(1)

    try:
        # Step 1: Get current pod and the node it is running on
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
        node_name = pod.spec.node_name
        print(f"Current pod {pod_name} (ns={namespace}) is running on node: {node_name}")

        # Step 2: Get all pods on that node, filter out kube-system
        pods_on_node = v1.list_pod_for_all_namespaces(field_selector=f"spec.nodeName={node_name}")
        filtered_pods = [p for p in pods_on_node.items if p.metadata.namespace != "kube-system"]

        print("Pods on the same node (excluding kube-system):")
        for p in filtered_pods:
            print(f" - {p.metadata.name} (ns={p.metadata.namespace})")

        # Step 3: Match pods to Services
        services = v1.list_service_for_all_namespaces().items
        pod_to_service = {}

        for svc in services:
            if not svc.spec.selector:
                continue

            for pod in filtered_pods:
                pod_labels = pod.metadata.labels or {}
                if all(pod_labels.get(k) == v for k, v in svc.spec.selector.items()):
                    pod_to_service[pod.metadata.name] = svc.metadata.name

        for pod_name, svc_name in pod_to_service.items():
            print(f"Pod {pod_name} is part of Service {svc_name}")

        # Step 4: Verify all pods are running
        not_running = []
        for pod in filtered_pods:
            if pod.status.phase != "Running":
                not_running.append(pod.metadata.name)

        if not_running:
            print("❌ The following pods are not running:", not_running)
            exit(1)
        else:
            print("✅ All pods on the node (excluding kube-system) are running.")

    except ApiException as e:
        print(f"Exception when calling CoreV1Api: {e}")
        exit(1)


if __name__ == "__main__":
    main()
