#----------------------------------------------------------------------------
# NVMe Test Logger
# Created by: Yuliang Tao (taoyl@marvell.com)
# Created at: Wed Nov  8 10:09:29 CST 2017
#----------------------------------------------------------------------------

import sys
import logging

class NvmeLogger(object):
    """
    Nvme Logger, logging all outputs to a log file.
    """

    def __init__(self, logger, level=logging.INFO):
        self.logger  = logger
        self.level   = level
        #self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.level, line.rstrip())

    def flush(self):
        pass


