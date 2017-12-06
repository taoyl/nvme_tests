#----------------------------------------------------------------------------
# NVMe IO Test
# Created by: Yuliang Tao (taoyl@marvell.com)
# Created at: Tue Nov  7 11:08:09 CST 2017
#----------------------------------------------------------------------------

# Satndard libraries
import os
import re
import sys
import math
import glob
import random
import filecmp
import subprocess

# Third-party libraries
from nose import tools
from nose.tools import assert_equal

# User-defined libraries
from test_nvme import TestNvme
from nvme_utils import exec_shell_cmd, calc_avg_bw


TIME_UNIT = {'us': 0.000001, 'ms': 0.001, 's': 1}


class TestNvmeIo(TestNvme):
    """
    Class for Nvme Io Tests.
    """

    def __init__(self, cfg=None):
        TestNvme.__init__(self)

        self.data_bytes = 4096
        self.slba       = 0
        self.nlb        = 0
        self.wr_file    = "data/wr.dat"
        self.rd_file    = "data/rd.dat"

        if not os.path.exists('data'):
            os.makedirs('data')

        self.__clear_rd_file()

    @classmethod
    def setup_class(cls):
        TestNvme.validate_pci_device();

    @classmethod
    def teardown_class(cls):
        pass

    @tools.nottest
    def __clear_rd_file(self):
        open(self.rd_file, 'w').close()

    @tools.nottest
    def __gen_rand_data_file(self, num_dws=1024):
        with open(self.wr_file, 'w') as wf:
            for i in range(num_dws):
                dw = [random.choice('0123456789ABCDEF') for x in range(4)]
                #wf.write(''.join(dw).encode('utf-8'))
                wf.write(''.join(dw))
        return True 

    @tools.nottest
    def __get_rand_video_file(self):
        files = ('small.mp4', 'medium.mp4', 'large.mp4')
        fid = random.randint(0, len(files)-1)
        return files[fid]

    @tools.nottest
    def __get_latency(self, text, use_dd=False):
        """
        Get the latency and return its value based on second.
        """
        # if use_dd:
        #     mat = re.search(r'copied,\s+([\.\d]+)\s+(\w+)', text)
        # else:
        #     mat = re.search(r'latency:.*([\.\d]+)\s+(\w+)', text) 
        pat = r'{prefix}[^\.\d]+([\.\d]+)\s+(\w+)'.format(
                prefix=r'copied,' if use_dd else r'latency:')
        mat = re.search(pat, text)
        if not mat:
            print(text, file=sys.stderr)
            return

        value  = mat.group(1) 
        unit   = mat.group(2) 
        assert_equal(unit in TIME_UNIT, True, unit)
        latency = float(value) * TIME_UNIT[unit]
        # print("val={} unit={} get latency={} s".format(value, unit, latency))
        return latency

    @tools.nottest
    def __io_rw_args(self, slba, nlb, num_bytes, fname):
        return ('--start-block={} --block-count={} --data-size={} --data={}'
                ' --latency'.format(slba, nlb, num_bytes, fname))

    @tools.nottest
    @calc_avg_bw("Read")
    def io_read(self, slba, nlb, num_bytes, fname, use_dd=False, bwlog_en=False, cmdlog_en=False):

        if not use_dd:
            kwargs = {'ns1': self.ns1, 
                    'args': self.__io_rw_args(slba, nlb, num_bytes, fname)}
            status, lines = self._read(**kwargs)
        else:
            # must use iflag to support exact-byte read
            cmd = ("dd if={0} of={1} ibs={3} count={2} obs={2} skip={4}"
                    " iflag=count_bytes").format(
                    self.ns1, fname, num_bytes, self.lba_ds, slba)
            status, lines = exec_shell_cmd(cmd, cmdlog_en)

        latency = self.__get_latency(' '.join(lines), use_dd)
        return status, (num_bytes, latency)

    @tools.nottest
    @calc_avg_bw("Write")
    def io_write(self, slba, nlb, num_bytes, fname, use_dd=False, bwlog_en=False, cmdlog_en=False):
        if not use_dd:
            kwargs = {'ns1': self.ns1, 
                    'args': self.__io_rw_args(slba, nlb, num_bytes, fname)}
            status, lines = self._write(**kwargs)
        else:
            cmd = "dd if={1} of={0} ibs={2} count={3} obs={4} seek={5}".format(
                    self.ns1, fname, num_bytes, 1, self.lba_ds, slba)
            status, lines = exec_shell_cmd(cmd, cmdlog_en)

        latency = self.__get_latency(' '.join(lines), use_dd)
        return status, (num_bytes, latency)

    def test_rand_data_xfer(self):
        """
        Test random data transfer using IO read/write command
        """
        self.get_ns_info()
        loops = 5
        bwlog_en = False
        for i in range(loops):
            bwlog_en = True if i == loops-1 else False
            self.__clear_rd_file()

            # randomize the data bytes and destination lba, up to 4 LBA data size
            num_dws = random.randint(1, self.lba_ds)
            #num_dws = 256 * 1024 * 10
            nlb = math.ceil(num_dws * 4.0 / self.lba_ds)
            max_lba_id = self.max_lba - nlb
            slba = random.randint(0, max_lba_id)
            # NLB uses 0's based value
            nlb -= 1
            print("Random Data: DW_NUM={}, SLBA={}, NLB={}".format(num_dws, hex(slba), hex(nlb)))

            assert_equal(self.__gen_rand_data_file(num_dws), True)
            assert_equal(self.io_write(slba, nlb, num_dws<<2, self.wr_file, bwlog_en=bwlog_en), 0)
            assert_equal(self.io_read(slba, nlb, num_dws<<2, self.rd_file, bwlog_en=bwlog_en), 0)
            assert_equal(filecmp.cmp(self.wr_file, self.rd_file), True)

    def test_bulk_data_xfer(self):
        """
        Test bulk data transfer using dd command 
        """
        wr_file = 'data/{}'.format(self.__get_rand_video_file())
        if not os.path.exists(wr_file):
            return False 

        self.get_ns_info()
        num_bytes = os.path.getsize(wr_file)
        # zero's based
        nlb = math.ceil(num_bytes * 1.0 / self.lba_ds)
        max_lba_id = self.max_lba - nlb
        slba = random.randint(0, max_lba_id)
        # NLB uses 0's based value
        nlb -= 1
        print("Data: BYTE_NUM={}, SLBA={}, NLB={}".format(num_bytes, hex(slba), hex(nlb)))

        assert_equal(self.io_write(slba, nlb, num_bytes, wr_file, use_dd=True, bwlog_en=True, cmdlog_en=True), 0)
        assert_equal(self.io_read(slba, nlb, num_bytes, self.rd_file, use_dd=True, bwlog_en=True, cmdlog_en=True), 0)
        assert_equal(filecmp.cmp(wr_file, self.rd_file), True)

    def test_bulk_data_xfer_128k(self):
        """
        Test bulk data transfer (splitted into multi 128K) using IO read/write command
        Since nvme-cli supports only 128K bytes in a single IO Read/Write,
        we need to split the large file into multiple 128K files.
        """
        wr_file = 'data/{}'.format(self.__get_rand_video_file())
        if not os.path.exists(wr_file):
            return False 

        self.get_ns_info()
        num_bytes = os.path.getsize(wr_file)
        # zero's based
        nlb = math.ceil(num_bytes * 1.0 / self.lba_ds)
        max_lba_id = self.max_lba - nlb
        slba = random.randint(0, max_lba_id)
        # NLB uses 0's based value
        nlb -= 1
        print("Data: BYTE_NUM={}, SLBA={}, NLB={}".format(num_bytes, hex(slba), hex(nlb)))

        max_support_bytes = 128 * 1024
        if num_bytes > max_support_bytes:
            # delete all intermidate files
            subprocess.call(r'rm -f data/wrsplit* data/rdsplit*', shell=True)
            # write
            cmd = r'split --bytes=128K {} data/wrsplit'.format(wr_file)
            subprocess.call(cmd, shell=True)
            curr_slba = slba
            file_sizes = []
            split_files = sorted(glob.glob('data/wrsplit*'))
            for f in split_files:
                size = os.path.getsize(f)
                file_sizes.append(size)
                nlb = math.ceil(size * 1.0 / self.lba_ds)
                bwlog_en = True if len(file_sizes) == len(split_files) else False
                #print("Write {} bytes from file {} to LBA{}".format(size, f, curr_slba))
                assert_equal(self.io_write(curr_slba, nlb-1, size, f, bwlog_en=bwlog_en), 0)
                curr_slba += nlb
            # read
            curr_slba = slba
            for i, size in enumerate(file_sizes):
                f = 'data/rdsplit{:04d}'.format(i)
                nlb = math.ceil(size * 1.0 / self.lba_ds)
                bwlog_en = True if len(file_sizes)-1 == i else False
                #print("Read {} bytes from LBA{} to file {}".format(size, curr_slba, f))
                assert_equal(self.io_read(curr_slba, nlb-1, size, f, bwlog_en=bwlog_en), 0)
                curr_slba += nlb
            err = subprocess.call(r'cat data/rdsplit* > {}'.format(self.rd_file), shell=True)
            assert_equal(err, 0, "ERROR: failed to merge read files ")
            # delete all intermidate files
            subprocess.call(r'rm -f data/wrsplit* data/rdsplit*', shell=True)
        else:
            assert_equal(self.io_write(slba, nlb, num_bytes, wr_file), 0)
            assert_equal(self.io_read(slba, nlb, num_bytes, self.rd_file), 0)

        # sanity check
        assert_equal(filecmp.cmp(wr_file, self.rd_file), True)

    def test_data_compare(self):
        """
        Compare the data between host and device using compare command
        """
        pass

    def test_write_zeros(self):
        """
        Write zeros to non-zero LBAs and check if the command works 
        """
        pass


