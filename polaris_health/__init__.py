#-*- coding: utf-8 -*-


class Error(Exception):

    """Generic exception"""

    pass


class ProtocolError(Error):

    """Protocol error, used by protocols"""

    pass


class MonitorFailed(Error):

    """Exception to signal health check failure, used by monitors"""

    pass


from polaris_health.runtime import Runtime


# application entry point
def start():
    Runtime().start()

