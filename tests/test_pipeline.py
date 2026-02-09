from agents.coordinator import Coordinator
from agents.analyst import AnalystAgent
from agents.policy import PolicyAgent

agents = [
    AnalystAgent(),
    PolicyAgent(policies={})
]

coordinator = Coordinator(agents)

event = {
    "type": "anomaly_detected",
    "service": "AWS EC2",
    "metric": "network_out",
    "value": "10x baseline"
}

events = coordinator.dispatch(event)

for e in events:
    print("\n" + "="*50 + "\n")
    print(e)
    print("\n" + "="*50 + "\n")