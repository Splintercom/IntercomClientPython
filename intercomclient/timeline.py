
class Timeline:
    def __init__(self, client):
        self.client = client

    def add_event(self, timestamp, data, live):
        event = {
            "timestamp": timestamp,
            "data": data,
            "live": live
        }
