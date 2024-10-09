from metrics.base_metric import BaseMetric
from time import monotonic_ns

class StopWatch(BaseMetric):
    def __init__(self, commands):
        super().__init__(commands)
        self.total = 0
    def before_command(self,command):
        self.start = monotonic_ns()
    def after_command(self,command, result):
        time_elapsed = monotonic_ns()-self.start
        self.total+= time_elapsed
    def get_result(self):
        return self.total / 1e9