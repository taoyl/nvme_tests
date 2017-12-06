#----------------------------------------------------------------------------
# NVMe IO Test
# Created by: Yuliang Tao (taoyl@marvell.com)
# Created at: Tue Nov  7 11:08:09 CST 2017
#----------------------------------------------------------------------------

# Satndard libraries
import sys
import math
import random
import filecmp
import logging
import subprocess

# Third-party libraries
from nose import tools
from nose.tools import assert_equal

# User-defined libraries
from test_nvme import TestNvme


class TestNvmeAdmin(TestNvme):
    """
    Class for Nvme Io Tests.
    """

    def __init__(self, cfg=None):
        TestNvme.__init__(self)

    @classmethod
    def setup_class(cls):
        TestNvme.validate_pci_device();

    @classmethod
    def teardown_class(cls):
        pass

    def test_init(self):
        """
        Test NVMe initialization
        """
        kwargs = {'ns1': self.ns1, 'args': ''}
        status, lines = self._id_ctrl(**kwargs)
        assert_equal(status, 0, ''.join(lines))
        mn = lines[4].split(r':')[1].strip()
        fr = lines[5].split(r':')[1].strip()
        print("NVMe Info: mn={}, fr={}".format(mn, fr))
        assert_equal(mn, 'MARVELL - Zao', "{} got, not MARVELL ZAO".format(mn))

