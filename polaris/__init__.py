#-*- coding: utf-8 -*-

import logging
import logging.config

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

class Error(Exception):

    """Generic exception"""

    pass

class ProtocolError(Error):

    """Protocol error, used by protocols"""

    pass


class MonitorFailed(Error):

    """Exception to signal health check failure, used by monitors"""

    pass

# import config into the local namespace
from . import config

