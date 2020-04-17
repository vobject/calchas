import logging
import queue
import threading
import time
from typing import Any, Dict, List

from calchas import monitor


class MonitoredSensor:
    def __init__(self, options: Any, healthmon: monitor.HealthMonitor):
        super().__init__()
        self._options = options
        self._healthmon = healthmon

    @property
    def name(self):
        return self.options["name"]

    @property
    def options(self):
        return self._options

    @property
    def dry_run(self):
        return self.options.get("dry-run", False)

    @property
    def out_dir(self):
        return self.options["out_dir"]

    def monitor(self, entry: Any):
        self._healthmon.on_report(monitor.HealthEntry(self, entry))

    def start(self):
        try:
            self._start_impl()
        except Exception:
            logging.exception(f"Error starting {self.name}")

    def stop(self):
        try:
            self._stop_impl()
        except Exception:
            logging.exception(f"Error stopping {self.name}")

    def _start_impl(self):
        raise NotImplementedError

    def _stop_impl(self):
        raise NotImplementedError


class SensorBase:
    def __init__(self, options: Any):
        self._options = options

    @property
    def options(self):
        return self._options

    @property
    def name(self):
        return self.options["name"]

    @property
    def dry_run(self):
        return self.options.get("dry-run", False)

    @property
    def out_dir(self):
        return self.options["out_dir"]


class Message:
    def __init__(self, sensor: SensorBase, topic: str, data: Any):
        self.timestamp = int(time.time() * 1000)
        self.sensor = sensor
        self.topic = topic
        self.data = data


class Subscriber:
    def __init__(self, options: Any):
        super().__init__()
        self._options = options
        self._messages = None
        self._message_thread = None
        self._run_message_thread = False

    @property
    def options(self) -> Any:
        return self._options

    @property
    def name(self) -> str:
        return self.options["name"]

    @property
    def dry_run(self) -> bool:
        return self.options.get("dry-run", False)

    @property
    def out_dir(self) -> str:
        return self.options["out_dir"]

    #@property
    #def request_stop(self) -> bool:
    #    raise NotImplementedError

    def on_process_message(self, msg: Message) -> None:
        raise NotImplementedError

    def on_message(self, msg: Message) -> None:
        if self._run_message_thread:
            self._messages.put(msg)

    def start(self):
        try:
            self._start_impl()

            self._run_message_thread = True
            self._messages = queue.Queue()
            self._message_thread = threading.Thread(target=self._consume_message_thread_fn)
            self._message_thread.start()
        except NotImplementedError:
            raise
        except Exception:
            logging.exception(f"Error starting {self.name}")

    def stop(self):
        try:
            self._run_message_thread = False
            if self._message_thread:
                self._message_thread.join()
                self._message_thread = None
            self._messages = queue.Queue()

            self._stop_impl()
        except NotImplementedError:
            raise
        except Exception:
            logging.exception(f"Error stopping {self.name}")

    def _start_impl(self):
        raise NotImplementedError

    def _stop_impl(self):
        raise NotImplementedError


    def _consume_message_thread_fn(self) -> None:
        while self._run_message_thread:
            try:
                msg = self._messages.get(True, 1.)
            except queue.Empty:
                continue

            self.on_process_message(msg)


class Publisher(SensorBase):
    def __init__(self, options: Any):
        super().__init__(options)
        self._subscribers: Dict[str, List[Subscriber]] = {}

    def offer(self) -> List[str]:
        # Offered sensors may not change during lifetime of object.
        raise NotImplementedError

    def subscribe(self, subscriber: Subscriber, topic: str=None):
        if topic:
            subs = self._subscribers.get(topic, [])
            if not subscriber in subs:
                subs.append(subscriber)
                self._subscribers[topic] = subs
        else:
            # Subscribe to all topics
            for t in self.offer():
                self.subscribe(subscriber, t)

    def unsubscribe(self, subscriber: Subscriber, topic: str=None):
        if topic:
            for t, subs in self._subscribers.items():
                if t == topic and subscriber in subs:
                    subs.remove(subscriber)
        else:
            # Unsubscribe from all topics
            for t in self.offer():
                self.unsubscribe(subscriber, t)

    def publish(self, topic: str, payload: Any) -> None:
        for t, subs in self._subscribers.items():
            if t == topic:
                for s in subs:
                    s.on_message(Message(self, topic, payload))

    def start(self):
        try:
            self._start_impl()
        except NotImplementedError:
            raise
        except Exception:
            logging.exception(f"Error starting {self.name}")

    def stop(self):
        try:
            self._stop_impl()
        except NotImplementedError:
            raise
        except Exception:
            logging.exception(f"Error stopping {self.name}")

    def _start_impl(self):
        raise NotImplementedError

    def _stop_impl(self):
        raise NotImplementedError
