from typing import List, Dict, Any
from agents.base import BaseAgent

class Coordinator:
    def __init__(self, agents: List[BaseAgent]):
        self.agents = agents

    def dispatch(self, initial_event: Dict[str, Any]) -> List[Dict[str, Any]]:
        event_queue = [initial_event]
        processed_events = []
        
        # Safety limit to prevent infinite loops
        max_iterations = 10
        iterations = 0

        while event_queue and iterations < max_iterations:
            current_event = event_queue.pop(0)
            iterations += 1
            
            # Don't re-process events that we've already seen as *outputs* 
            # (though in this simple version, we process everything in the queue)

            is_handled = False
            for agent in self.agents:
                try:
                    if agent.can_handle(current_event):
                        is_handled = True
                        print(f"\n[Coordinator] Dispatching '{current_event.get('type')}' to {agent.name}...")
                        
                        result = agent.handle(current_event)
                        
                        if result:
                            # Add result to queue for further processing
                            event_queue.append(result)
                            processed_events.append(result)
                            
                except Exception as e:
                    error_event = {
                        "type" : "agent_error",
                        "source_agent" : agent.name,
                        "error" : str(e),
                        "original_event" : current_event
                    }
                    processed_events.append(error_event)
            
            if not is_handled and iterations > 1:
                 # Log unhandled events (excluding the initial one if needed, but here we just log)
                 # print(f"Warning: No agent handled event type: {current_event.get('type')}")
                 pass

        return processed_events