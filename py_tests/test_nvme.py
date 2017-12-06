#----------------------------------------------------------------------------
# NVMe Test Base
# Created by: Yuliang Tao (taoyl@marvell.com)
# Created at: Mon Nov  6 16:46:27 CST 2017
#----------------------------------------------------------------------------

# Satndard libraries
import os
import re
import sys
import json
import subprocess

# Third-party libraries
from nose import tools
from nose.tools import assert_equal

# User-defined libraries
from nvme_utils import NvmeCli


class TestNvme(object):
    """
    Base class for Nvme Tests.
    """

    def __init__(self):
        """
        @param cfg: Config file (json format) used to set controller, default namespace, etc.
        """
        #if cfg is None:
        cfg = "nvme.json"
        self.ctrler    = "/dev/nvme0"
        self.ns1       = "/dev/nvme0n1"
        self.max_lba   = 1 << 17
        self.lba_ds    = 4096

        if os.path.exists(cfg):
            self._load_config(cfg)

    def _load_config(self,  fname):
        with open(fname, 'r') as cfg:
            configs = json.load(cfg)
            self.ctrler  = configs['ctrler']
            self.ns1     = configs['ns1']

    @tools.nottest
    @staticmethod
    def validate_pci_device():
        cmd = r'find /sys/devices -name \*nvme0 | grep -i pci'
        err = subprocess.call(cmd, shell=True)
        assert_equal(err, 0, "ERROR: no NVMe devices found")

    @tools.nottest
    @NvmeCli(opc='control-test', vendor='marvell')
    def _control_test(self, *args, **kwargs):
        return args

    @tools.nottest
    @NvmeCli(opc='read')
    def _read(self, *args, **kwargs):
        return args

    @NvmeCli(opc='write')
    def _write(self, *args, **kwargs):
        return args

    @NvmeCli(opc='id-ns')
    def _id_ns(self, *args, **kwargs):
        return args

    @NvmeCli(opc='id-ctrl')
    def _id_ctrl(self, *args, **kwargs):
        return args

    @tools.nottest
    def query_tests(self, test_bitmap):
        kwargs = {'cmdlog_en': True,
                'ns1': self.ns1, 
                'args': '--query --test-list={}'.format(test_bitmap)}
        status, lines = self._control_test(**kwargs)
        assert_equal(status, 0, ''.join(lines))
        lines = ' '.join(lines)
        mat = re.search(r'Test\s+IDs=(\w+)', lines) 
        if not mat:
            print("*** No valid tests found from device", file=sys.stderr)
            return 0
        return int(mat.group(1), 16)

    @tools.nottest
    def report_status(self, control, status_bitmap, bwf=None, bws=0):
        """
        Report test status to device controller.
        """
        bw_info = ''
        if bwf and bws:
            bw_info = '--bwfile={} --bwsize={}'.format(bwf, bws)

        kwargs = {'cmdlog_en': True,
                'ns1': self.ns1, 
                'args': '--control={} --status={} {}'.format(
                        hex(control), hex(status_bitmap), bw_info)}
        status, lines = self._control_test(**kwargs)
        assert_equal(status, 0, ''.join(lines))

    @tools.nottest
    def get_ns_info(self):
        """
        Get namespace size and LBA data size.
        """
        # default size
        kwargs = {'ns1': self.ns1, 'args': ''} 
        status, lines = self._id_ns(**kwargs)
        assert_equal(status, 0, ''.join(lines))

        lines = ' '.join(lines)
        pat_lbaf = re.compile(r'lbaf\s+\d+.*lbads:(\d+).*in use')
        pat_nsze = re.compile(r'nsze\s+:\s+(\w+)')
        mat = pat_nsze.search(lines)
        if mat:
            self.max_lba = int(mat.group(1), 16)
        mat = pat_lbaf.search(lines)
        if mat:
            self.lba_ds = 2**int(mat.group(1))
        print("NSZE={}, LBADS={}".format(self.max_lba, self.lba_ds))
        
