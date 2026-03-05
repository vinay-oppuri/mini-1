import re


class DrainParser:

    def __init__(self):
        self.template_to_id = {}
        self.next_id = 1

    def parse(self, logs):
        results = []

        for log in logs:
            raw = str(log).strip()
            if not raw:
                continue

            text = raw.lower()

            # replace IP addresses
            text = re.sub(r"\d+\.\d+\.\d+\.\d+", "<*>", text)

            # replace numbers
            text = re.sub(r"\d+", "<*>", text)

            template = text

            # assign event id
            if template not in self.template_to_id:
                self.template_to_id[template] = "E" + str(self.next_id)
                self.next_id += 1

            event_id = self.template_to_id[template]

            results.append({
                "raw": raw,
                "template": template,
                "event_id": event_id
            })

        return results
