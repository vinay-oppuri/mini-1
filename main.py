import json
from agents.coordinator import Coordinator

# sample logs if file fails
MOCK_LOGS = [
    "ERROR auth-service: Login failed for user admin from IP 203.0.113.10",
    "ERROR auth-service: Login failed for user admin from IP 203.0.113.10",
    "ERROR auth-service: Login failed for user admin from IP 203.0.113.10",
    "WARN api-gateway: Too many requests from IP 203.0.113.10 status 429",
    "WARN api-gateway: Too many requests from IP 203.0.113.10 status 503",
]


# function to load logs from json file
def load_logs(file_path):

    try:
        file = open(file_path, "r")
        logs = json.load(file)
        file.close()

        return logs, "REAL DATA", ""

    except Exception as error:
        reason = f"Could not load real logs file: {error}"
        print(reason)
        print("Using mock logs instead.")
        return MOCK_LOGS, "MOCK DATA", reason


# function to print results nicely
def print_report(result, data_source, fallback_reason):

    analysis = result["analysis"]
    llm = result["llm_explanation"]
    policy = result["policy"]
    response = result["response"]
    metrics = result["cloud_metrics"]

    # show where output came from
    print("\nDATA SOURCE:", data_source)
    if data_source == "MOCK DATA" and fallback_reason != "":
        print("Reason:", fallback_reason)

    # anomaly or not
    if analysis["is_anomaly"]:
        print("\nANOMALY DETECTED\n")
    else:
        print("\nNO CRITICAL ANOMALY\n")

    print("Service:", metrics["service"])
    print("Score:", analysis["anomaly_score"])

    print("\nGemini Analysis")
    print("Attack Type:", llm["attack_type"])
    print("Reason:", llm["reason"])

    print("\nAction")

    actions = response["actions"]

    if len(actions) == 0:
        print("- No action needed")
    else:
        for action in actions:
            print("-", action)

    print("\nSeverity:", policy["severity"])


# main program
def main():

    # create coordinator (multi-agent system)   
    coordinator = Coordinator()

    # load logs
    logs, data_source, fallback_reason = load_logs("data/raw_logs/app/cloud_workload_logs.json")

    # run detection (if real-data processing fails, retry with mock data)
    try:
        result = coordinator.run(logs=logs, source="cloud-workload")

    except Exception as error:
        if data_source == "MOCK DATA":
            raise

        fallback_reason = f"Could not process real data output: {error}"
        print(fallback_reason)
        print("Retrying with mock logs...")

        logs = MOCK_LOGS
        data_source = "MOCK DATA"
        result = coordinator.run(logs=logs, source="mock-fallback")

    # show result
    print_report(result, data_source, fallback_reason)


if __name__ == "__main__":
    main()
