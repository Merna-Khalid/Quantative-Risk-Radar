import asyncio

class SignalObserver:
    def __init__(self):
        self._subscribers = []

    def attach(self, callback):
        self._subscribers.append(callback)

    async def notify(self, event_data):
        for callback in self._subscribers:
            if asyncio.iscoroutinefunction(callback):
                await callback(event_data)
            else:
                callback(event_data)

def log_event(event):
    print(f"[LOG] Signal processed: {event}")

async def notify_dashboard(event):
    await asyncio.sleep(0.2)  # simulate async dashboard update
    print(f"[DASHBOARD] Updated for signal {event['id']}")