from agents.analyst import AnalystAgent

event = {
    "type": "anomaly_detected",
    "service" : "AWS EC2",
    "metric" : "network_outbound",
    "value" : "12x baseline",
    "duration" : "180s",
    "source_ip" : "185.xxx.xxx.xxx"
}

agent = AnalystAgent()

if agent.can_handle(event):
    result = agent.handle(event)
    print("\n--- AGENT OUTPUT ---\n")
    print(result)
else:
    print("\n--- AGENT CANNOT HANDLE THIS EVENT ---\n")