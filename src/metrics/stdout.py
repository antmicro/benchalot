from metrics.base_metric import BaseMetric
class StdOutCatcher(BaseMetric):
    def __init__(self, commands):
        super().__init__(commands)
        self.stdout = ''
    def before_command(self, command):
        pass
    def after_command(self, command, result):
        self.stdout +=result.stdout.decode("utf-8").strip()
    def get_result(self):
        return self.stdout