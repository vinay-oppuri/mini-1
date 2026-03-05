import json
import random
from datetime import datetime, timedelta

# where logs will be saved
OUTPUT_FILE = "cloud_logs.json"

services = ["auth-service", "api-gateway", "k8s-pod-a", "ml-trainer"]
users = ["alice", "bob", "carol", "dave", "admin"]

internal_ips = ["10.0.1." + str(i) for i in range(10,50)]
external_ips = ["203.0.113." + str(i) for i in range(10,90)]


def generate_logs():

    logs = []
    start_time = datetime.now()

    for i in range(120):

        timestamp = start_time + timedelta(seconds=i)

        service = random.choice(services)
        user = random.choice(users)
        ip = random.choice(internal_ips)

        # Normal log
        log = {
            "timestamp": str(timestamp),
            "level": "INFO",
            "service": service,
            "message": f"User {user} accessed workload from {ip}"
        }

        logs.append(log)

    return logs


def main():

    logs = generate_logs()

    file = open(OUTPUT_FILE,"w")
    json.dump(logs,file,indent=2)
    file.close()

    print("Logs generated successfully")


main()