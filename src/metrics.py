from time import monotonic_ns


class BaseMetric:
    def __init__(self, commands):
        self.commands = commands

    def before_command(self, command):
        pass

    def after_command(self, command, result):
        pass

    def get_result(self):
        pass


class TimeMetric(BaseMetric):
    def __init__(self, commands):
        super().__init__(commands)
        self.total = 0

    def before_command(self, command):
        self.start = monotonic_ns()

    def after_command(self, command, result):
        time_elapsed = monotonic_ns() - self.start
        self.total += time_elapsed

    def get_result(self):
        return self.total / 1e9


class StdOutMetric(BaseMetric):
    def __init__(self, commands):
        super().__init__(commands)
        self.stdout = ""

    def before_command(self, command):
        pass

    def after_command(self, command, result):
        self.stdout += result.stdout.decode("utf-8").strip()

    def get_result(self):
        return self.stdout
