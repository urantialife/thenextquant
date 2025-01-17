# -*- coding:utf-8 -*-

"""
Asynchronous driven quantitative trading framework.

Author: HuangTao
Date:   2017/04/26
Email:  huangtao@ifclover.com
"""

import signal
import asyncio

from quant.utils import logger
from quant.config import config


class Quant:
    """ Asynchronous driven quantitative trading framework.
    """

    def __init__(self):
        self.loop = None
        self.event_center = None

    def initialize(self, config_module=None):
        """ Initialize.

        Args:
            config_module: config file path, normally it"s a json file.
        """
        self._get_event_loop()
        self._load_settings(config_module)
        self._init_logger()
        self._init_db_instance()
        self._init_event_center()
        self._init_http_server()
        self._do_heartbeat()

    def start(self):
        """Start the event loop."""
        def keyboard_interrupt(s, f):
            print("KeyboardInterrupt (ID: {}) has been caught. Cleaning up...".format(s))
            self.loop.stop()
        signal.signal(signal.SIGINT, keyboard_interrupt)

        logger.info("start io loop ...", caller=self)
        self.loop.run_forever()

    def stop(self):
        """Stop the event loop."""
        logger.info("stop io loop.", caller=self)
        self.loop.stop()

    def _get_event_loop(self):
        """ Get a main io loop. """
        if not self.loop:
            self.loop = asyncio.get_event_loop()
        return self.loop

    def _load_settings(self, config_module):
        """ Load config settings.

        Args:
            config_module: config file path, normally it"s a json file.
        """
        config.loads(config_module)

    def _init_logger(self):
        """Initialize logger."""
        console = config.log.get("console", True)
        level = config.log.get("level", "DEBUG")
        path = config.log.get("path", "/tmp/logs/Quant")
        name = config.log.get("name", "quant.log")
        clear = config.log.get("clear", False)
        backup_count = config.log.get("backup_count", 0)
        if console:
            logger.initLogger(level)
        else:
            logger.initLogger(level, path, name, clear, backup_count)

    def _init_db_instance(self):
        """Initialize db."""
        if config.mongodb:
            from quant.utils.mongo import initMongodb
            initMongodb(**config.mongodb)

    def _init_event_center(self):
        """Initialize event center."""
        if config.rabbitmq:
            from quant.event import EventCenter
            self.event_center = EventCenter()
            self.loop.run_until_complete(self.event_center.connect())
            config.initialize()

    def _init_http_server(self):
        """Initialize HTTP server."""
        if not config.http_server:
            return

        import importlib
        from aiohttp import web
        from quant.utils.web import routes

        # load apis.
        for dir in config.http_server.get("apis"):
            s = "import %s" % dir
            exec(s)

        # load middlewares.
        middlewares = []
        for m in config.http_server.get("middlewares", []):
            x, y = m.rsplit(".", 1)
            moudle = importlib.import_module(x)
            m = getattr(moudle, y)
            middlewares.append(m)

        # print handlers..
        for route in routes:
            logger.info("registered api:", route.path, "method:", route.method, "handler:", route.handler, caller=self)

        host = config.http_server.get("host", "localhost")
        port = config.http_server.get("port")
        app = web.Application(middlewares=middlewares)
        app.add_routes(routes)
        runner = web.AppRunner(app)
        asyncio.get_event_loop().run_until_complete(runner.setup())
        site = web.TCPSite(runner, host, port)
        asyncio.get_event_loop().run_until_complete(site.start())
        logger.info("http server listen port on:", "%s:%s" % (host, port), caller=self)

    def _do_heartbeat(self):
        """Start server heartbeat."""
        from quant.heartbeat import heartbeat
        self.loop.call_later(0.5, heartbeat.ticker)


quant = Quant()
