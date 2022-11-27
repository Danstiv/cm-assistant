import logging
import time


class Formatter(logging.Formatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_msec_format = '%s,%03d %s'

    def formatTime(self, record, datefmt=None):
        ct = self.converter(record.created)
        t1 = time.strftime('%H:%M:%S', ct)
        t2 = time.strftime('%Y-%m-%d', ct)
        s = self.default_msec_format % (t1, record.msecs, t2)
        return s


class WarningErrorHandler(logging.Handler):

    def __init__(self, controller):
        super().__init__(logging.WARNING)
        self.controller = controller

    def emit(self, record):
        if record.levelno==logging.WARNING:
            type = 'warning'
        else:
            type = 'error'
        try:
            msg = self.format(record)
            self.controller.send_warning_error_message_sync(msg)
        except Exception:
            self.handleError(record)
