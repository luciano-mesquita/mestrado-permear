import time
from threading import Lock, Thread
from hardware.sensor import get_pressure


class SensorService:
    def __init__(self, hz=20):
        self.hz = hz
        self._lock = Lock()
        self._running = False
        self._thread = None
        self._latest_pressure = None
        self._latest_ts = 0.0
        self._last_error = None
        self._total_reads = 0
        self._total_errors = 0
        self._filtered_pressure = None
        self._alpha = 0.25

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = Thread(target=self._loop, daemon=True)
            self._thread.start()

    def stop(self):
        with self._lock:
            self._running = False
            thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=1.0)

    def _loop(self):
        intervalo = 1.0 / float(self.hz)
        while True:
            with self._lock:
                if not self._running:
                    break
            try:
                pressao = get_pressure()
                if self._filtered_pressure is None:
                    self._filtered_pressure = pressao
                else:
                    self._filtered_pressure = (self._alpha * pressao) + ((1 - self._alpha) * self._filtered_pressure)
                now = time.time()
                with self._lock:
                    self._latest_pressure = self._filtered_pressure
                    self._latest_ts = now
                    self._last_error = None
                    self._total_reads += 1
            except Exception as e:
                with self._lock:
                    self._last_error = str(e)
                    self._total_errors += 1
            time.sleep(intervalo)

    def get_latest_pressure(self, max_age_s=1.0):
        with self._lock:
            p = self._latest_pressure
            ts = self._latest_ts
            err = self._last_error

        # Se ainda não há leitura recente, faz fallback pontual direto.
        if p is None or (time.time() - ts) > max_age_s:
            p = get_pressure()
            with self._lock:
                self._latest_pressure = p
                self._latest_ts = time.time()
                self._last_error = None
            return p

        if err is not None and p is None:
            raise RuntimeError(err)

        return p

    def get_status(self):
        with self._lock:
            latest_age_s = (time.time() - self._latest_ts) if self._latest_ts else None
            return {
                "running": self._running,
                "latest_pressure": self._latest_pressure,
                "latest_age_s": latest_age_s,
                "last_error": self._last_error,
                "total_reads": self._total_reads,
                "total_errors": self._total_errors,
            }

    def reset_filter(self):
        with self._lock:
            self._filtered_pressure = None
            self._latest_pressure = None
            self._latest_ts = 0.0


sensor_service = SensorService(hz=20)
