#----------------------------------------------------------------------------
# NVMe Utilities
# Created by: Yuliang Tao (taoyl@marvell.com)
# Created at: Mon Nov  20 10:46:27 CST 2017
#----------------------------------------------------------------------------

# Satndard libraries
import subprocess
from functools import wraps


def exec_shell_cmd(cmd, cmdlog_en=False):
    if cmdlog_en:
        print('EXEC_SHELL_CMD: {}'.format(cmd))
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT)
    status = proc.wait()
    text = [x.decode('utf-8').rstrip() for x in proc.stdout.readlines()] 
    return status, text 


def calc_avg_bw(t=""):
    def outer(func):
        num_bytes, seconds = (0, 0)
        @wraps(func)
        def inner(*args, **kwargs):
            nonlocal num_bytes, seconds
            status, bw = func(*args, **kwargs)
            num_bytes += bw[0]
            seconds += bw[1]
            if seconds == 0:
                avg_bw = 0.0 
            else:
                avg_bw = num_bytes / (1024.0 * 1024.0 * seconds)
            if kwargs.get('bwlog_en', False):
                print(('Accumulated {}: latency = {} s, num_bytes = {}, average '
                       'bandwidth = {} MB/s').format(t, seconds, num_bytes, avg_bw))
            return status
        return inner 
    return outer


class NvmeCli(object):
    
    def __init__(self, opc='', vendor=''):
        self.__opc    = opc
        self.__vendor = vendor
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            opcode = self.__opc or kwargs['opc']
            cmd = 'nvme {v} {opc} {ns1} {args}'.format(
                    v=self.__vendor, opc=opcode, **kwargs)
            status, lines = exec_shell_cmd(cmd, kwargs.get('cmdlog_en', False))
            args += (status, lines)
            return func(*args, **kwargs)
        return wrapper


