#!/usr/bin/python
from multiprocessing import Process
import os
import time

class Scanner(object):

    interface = None
    freqlist = range(2412,2467,5)
    process = None
    debugfs_dir = None
    is_ath10k = False

    def _find_debugfs_dir(self):
        ''' search debugfs for spectral_scan_ctl for this interface '''
        netdev_dir = 'netdev:%s' % self.interface
        for dirname, subd, files in os.walk('/sys/kernel/debug/ieee80211'):
            if 'spectral_scan_ctl' in files:
                if os.path.exists('%s/../%s' % (dirname, netdev_dir)):
                    return dirname
        return None

    def _start_collection(self):
        if self.is_ath10k:
            self.cmd_background()
        else:
            self.cmd_chanscan()

    def _scan(self):
        while True:
            if self.is_ath10k:
                self.cmd_trigger()

            cmd = 'iw dev %s scan' % self.interface
            if self.freqlist:
                cmd = '%s freq %s' % (cmd, ' '.join(self.freqlist))
            os.system('%s >/dev/null 2>/dev/null' % cmd)
            time.sleep(.01)

    def __init__(self, interface, freqlist=None):
        self.interface = interface
        self.freqlist = freqlist
        self.debugfs_dir = self._find_debugfs_dir()
        self.is_ath10k = self.debugfs_dir.endswith("ath10k")
        self.ctl_file = '%s/spectral_scan_ctl' % self.debugfs_dir
        if not self.debugfs_dir:
            raise Exception, \
                  'Unable to access spectral_scan_ctl file for interface %s' % interface

        self.process = Process(target=self._scan, args=())

    def cmd_trigger(self):
        f = open(self.ctl_file, 'w')
        f.write("trigger")
        f.close()

    def cmd_background(self):
        f = open(self.ctl_file, 'w')
        f.write("background")
        f.close()

    """def cmd_manual(self):
        f = open(self.ctl_file, 'w')
        f.write("manual")
        f.close()"""

    def cmd_chanscan(self):
        f = open(self.ctl_file, 'w')
        f.write("chanscan")
        f.close()

    def start(self):
        self._start_collection()
        self.process.start()

    def stop(self):
        self.process.terminate()
        self.process.join()

    def get_debugfs_dir(self):
        return self.debugfs_dir
