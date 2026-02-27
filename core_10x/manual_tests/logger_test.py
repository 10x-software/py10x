from core_10x.logger import Logger, LogMessage

m = LogMessage(_replace = True, payload = dict(a = 1, b = 'ccc'))
m.save()