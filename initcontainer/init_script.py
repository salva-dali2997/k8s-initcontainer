import os
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import logging
import sys

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


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
        print("❌ POD_NAME must be supplied as an environment variable.")
        exit(1)

    try:
        with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r") as f:
            namespace = f.read().strip()
    except Exception as e:
        print(f"❌ Unable to determine namespace: {e}")
        exit(1)

    # Step 0.1: Get required keywords from env
    pods_to_wait_for = os.getenv("PODS_TO_WAIT_FOR")
    if not pods_to_wait_for:
        print("❌ PODS_TO_WAIT_FOR must be supplied as a comma-separated environment variable.")
        exit(1)
    required_keywords = [kw.strip() for kw in pods_to_wait_for.split(",") if kw.strip()]

    try:
        # Step 1: Get current pod and the node it is running on
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
        node_name = pod.spec.node_name
        print(f"Current pod {pod_name} (ns={namespace}) is running on node: {node_name}")

        # Step 2: Get all pods on that node, filter out kube-system
        pods_on_node = v1.list_pod_for_all_namespaces(field_selector=f"spec.nodeName={node_name}")
        filtered_pods = [p for p in pods_on_node.items if p.metadata.namespace != "kube-system"]

        # Step 3: Check for required pods by name substrings
        missing_or_not_running = []

        for keyword in required_keywords:
            match = next((p for p in filtered_pods if keyword in p.metadata.name), None)
            if not match:
                missing_or_not_running.append(f"No pod found with name containing '{keyword}'")
            elif match.status.phase != "Running":
                missing_or_not_running.append(f"Pod {match.metadata.name} is {match.status.phase}")

        if missing_or_not_running:
            print("❌ Startup check failed:")
            for issue in missing_or_not_running:
                print(" -", issue)
            exit(1)
        else:
            print(f"✅ Required pods {required_keywords} are all running on the node.")

    except ApiException as e:
        print(f"Exception when calling CoreV1Api: {e}")
        exit(1)


if __name__ == "__main__":
    main()