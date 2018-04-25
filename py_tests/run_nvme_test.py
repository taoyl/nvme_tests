#----------------------------------------------------------------------------
# Test top
# Created by: Yuliang Tao (taoyl@marvell.com)
# Created at: Mon Nov 11 14:32:03 CST 2017
#----------------------------------------------------------------------------

# Standard libraries
import os
import re
import sys
import struct
import logging
import argparse
import subprocess
from functools import reduce
from datetime import datetime
from nose.tools import assert_equal

# User-defined libraries
from test_nvme import TestNvme
from nvme_logger import NvmeLogger

# NVMe Test IDs (Read-Only)
NVME_TESTS = (
    #           NAME                 ID     ENABLED                 TEST PATH                            FAIL? 
        ['NvmeTestNvmeInit'        , 0x01,  True,  'test_nvme_admin.py:TestNvmeAdmin.test_init'         , True],
        ['NvmeTestAdminCmds'       , 0x02,  False, 'test_nvme_admin.py:TestNvmeAdmin.test_admin_cmds'   , True],
        ['NvmeTestRandDataXfer'    , 0x04,  True,  'test_nvme_io.py:TestNvmeIo.test_rand_data_xfer'     , True],
        ['NvmeTestBulkDataXfer'    , 0x08,  True,  'test_nvme_io.py:TestNvmeIo.test_bulk_data_xfer'     , True],
        ['NvmeTestWriteZeros'      , 0x10,  False, 'test_nvme_io.py:TestNvmeIo.test_write_zeros'        , True],
        ['NvmeTestDataCompare'     , 0x20,  False, 'test_nvme_io.py:TestNvmeIo.test_data_compare'       , True],
        ['NvmeTestBulkDataXfer128K', 0x40,  True,  'test_nvme_io.py:TestNvmeIo.test_bulk_data_xfer_128k', True],
)


class RunTest(object):
    """
    Run Nvme Test.
    """

    def __init__(self, log_file, bw_file):
        self.bw_file = bw_file 
        self.log_file = log_file
        self.driver = TestNvme()
        self.sel_tests = [z for z in NVME_TESTS if z[2]]
        self.bw_size = 0

    def query(self):
        if len(self.sel_tests) == 1:
            test_bitmap = self.sel_tests[0][1]
        else:
            test_bitmap = reduce(lambda x,y: x | y, [z[1] for z in self.sel_tests])

        # update user-selected tests
        sel_ids = test_bitmap & self.driver.query_tests(test_bitmap)
        if sel_ids == 0:
            return False
        print("[Query]: user-selected test ids = {}".format(hex(sel_ids)))
        self.sel_tests = [z for z in self.sel_tests if z[1] & sel_ids]
        return True
            
    def start(self, test_ids=None):
        """
        Start test regression.
        """
        if test_ids:
            self.sel_tests = [x for x in self.sel_tests if x[1] & test_ids]
        print("Running {} tests in regression".format(len(self.sel_tests)))

        for item in self.sel_tests: 
            print("-" * 70)
            print("Test: {}".format(item[0]))
            cmd = 'nosetests -v --nocapture {}'.format(item[3])
            # nose uses sys.stderr as the default streaming, so we have to 
            # redirect stderr to stdout
            proc = subprocess.Popen(cmd, shell=True, 
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            proc.wait()
            for line in proc.stdout.readlines():
                print(line.decode('utf-8'))
            print("\n")

    def update_test_status(self):
        """
        Check and update test status.
        """
        if not os.path.exists(self.log_file):
            return

        with open(self.log_file, 'r') as log:
            lines = ''.join(log.readlines())

        sts_pat = re.compile(r'Test:\s+(\w+)[\S\s]+?Ran 1 test in.*\n.*?(FAILED|OK)')
        # check test status
        founds = sts_pat.findall(lines)
        if not founds:
            return
        for test in self.sel_tests:
           for res in founds:
               if test[0] == res[0]:
                   test[-1] = (res[1] == "FAILED")

        # check bw
        test_logs = lines.split(r'Test: ')
        bw_pat = re.compile((r'^(\w+)[\S\s]+?Ran 1 test in.*\n.*?OK[\S\s]+?'
                r'Write.*bandwidth = ([\.\d]+)[\S\s]+?Read.*bandwidth = ([\.\d]+)'))
        founds = []
        for tlog in test_logs:
            founds += bw_pat.findall(tlog)[:]
        if not founds:
            return

        bw_list = [(id, wbw, rbw) for name, wbw, rbw in founds 
                for n, id, *_ in self.sel_tests if n == name]
        dws = [hex(x)[2:].zfill(8) + self.float2hex(float(y)) + self.float2hex(float(z)) 
                for x, y, z in bw_list]
        if not len(dws):
            return

        # each DW consists of 8 characters
        self.bw_size = len(dws) * 3 * 8
        with open(self.bw_file, 'wb') as fh:
            fh.write(''.join(dws).encode('utf-8'))

    def float2hex(self, val):
        """
        Convert a float to IEEE-754 hex
        """
        ival = struct.unpack('<i', struct.pack('<f', val))[0]
        return hex(ival)[2:].zfill(8)

    def report_test_status(self):
        """
        Report test status to device controller.
        """
        self.update_test_status()
        fail_tests = [z for z in self.sel_tests if z[-1]]
        if len(fail_tests) == 1:
            status_bitmap = fail_tests[0][1]
        else:
            status_bitmap = reduce(lambda x,y: x | y, 
                    [z[1] for z in fail_tests], 0)
        print("[Report]: test status bitmap={}".format(hex(status_bitmap)))

        if os.path.exists(self.bw_file) and \
                (self.bw_size <= os.path.getsize(self.bw_file)):
            self.driver.report_status(0x3, status_bitmap, bwf=self.bw_file,
                    bws=self.bw_size)
        else:
            self.driver.report_status(0x1, status_bitmap)


def main():
    parser = argparse.ArgumentParser(prog='python {}'.format(sys.argv[0]), 
            description="Execute nvme tests")
    parser.add_argument('-d', '--debug', action='store_true',
            help="Run nvme tests in debug mode")
    parser.add_argument('-t', '--test', nargs='?', type=int, 
            help="Specify which tests will be executed")
    args = parser.parse_args()

    log_file = None
    bw_file = None
    if not args.debug:
        # create log directory
        td = datetime.today()
        log_dir = '{}/{}'.format('logs', td.strftime("%Y%m%d.%H%M%S"))
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_file = '{}/{}.log'.format(log_dir, "nvme")
        bw_file = '{}/bw.log'.format(log_dir)

        logging.basicConfig(
            level = logging.DEBUG,
            format = '%(asctime)s:%(levelname)s: %(message)s',
            filename = log_file,
            filemode = 'w'
        )
        sys.stdout = NvmeLogger(logging.getLogger('STDOUT'))
        sys.stderr = NvmeLogger(logging.getLogger('STDERR'), logging.ERROR)

    tester = RunTest(log_file, bw_file)
    if not args.debug and not tester.query():
        print('No test selected by user')
        return
    tester.start(args.test)
    if not args.debug:
        tester.report_test_status()


if __name__ == '__main__':
    main()

