class BaseMetric():
    def __init__(self, commands):
        self.commands = commands
    def before_command(self,command):
        pass
    def after_command(self,command,result):
        pass
    def get_result(self):
        pass