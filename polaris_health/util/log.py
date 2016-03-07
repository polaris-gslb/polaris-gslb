# -*- coding: utf-8 -*-

import logging
import logging.config

from polaris_health import Error, config

__all__ = [ 'setup', 'setup_debug' ]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'


class DatagramText(logging.handlers.DatagramHandler):

    """Override SocketHandler.emit() to emit plain text messages,
    as oppose to pickled logging.Record's
    """

    def __init__(self, *args, **kwargs):
        super(DatagramText, self).__init__(*args, **kwargs)

    def emit(self, record):
        try:
            # original emit() has "s = self.makePickle(record)" here
            s = self.format(record).encode()
            self.send(s)
        except Exception:
            self.handleError(record)


def setup():
    """Setup logging"""

    level = config.BASE['LOG_LEVEL']
    # validate level
    if level not in [ 'none', 'debug', 'info', 'warning', 'error' ]:
        log_msg = 'Unknown logging level "{}"'.format(level)
        LOG.error(log_msg)
        raise Error(log_msg)

    # do not setup logging if level is 'none'
    if level=='none':
        return

    handler = config.BASE['LOG_HANDLER']
    # validate handler
    if handler not in [ 'syslog', 'datagram' ]:
        log_msg = 'Unknown log handler "{}"'.format(handler)
        LOG.error(log_msg)
        raise Error(log_msg)

    hostname = config.BASE['LOG_HOSTNAME']
    port = config.BASE['LOG_PORT']

    # define common config dict elements
    log_config = {
        'version': 1,
        'disable_existing_loggers': False,

        'formatters': {
            'standard': {
                'format': FORMAT,
            },
        },

        'handlers': {},

        'loggers': {
            '': {
                'handlers': [ 'syslog' ],
                'level': level.upper(),
            },
        }
    }

    # add handler specific items
    if handler == 'syslog':
        log_config['handlers']['syslog'] = {
            'class': 'logging.handlers.SysLogHandler',
            'formatter': 'standard',
            'address': '/dev/log',
        }

        log_config['loggers']['']['handlers'] = [ 'syslog' ]
    
    elif handler == 'datagram':
        log_config['handlers']['datagram'] = {
            'class': 'polaris.util.logging.DatagramText',
            'formatter': 'standard',
            'host': hostname,
            'port': port,
        }
 
        log_config['loggers']['']['handlers'] = [ 'datagram' ]
        
    # initialize logging 
    logging.config.dictConfig(log_config)


def setup_debug():
    """Setup debug mode logging"""

    log_config = {
        'version': 1,
        'disable_existing_loggers': False,

        'formatters': {
            'standard': {
                'format': FORMAT,
            },
        },

        'handlers': {
            'console': {
                'class':'logging.StreamHandler',
                'formatter': 'standard',
            },

        },

        'loggers': {
            '': {
                'handlers': [ 'console' ],
                'level': 'DEBUG',
            },
        }

    }

    logging.config.dictConfig(log_config)

