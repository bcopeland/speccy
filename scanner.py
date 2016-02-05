#!/usr/bin/python
from multiprocessing import Process, Value
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
        if self.mode.value == 1:
            print "enter 'chanscan' mode: set dev type to 'managed'"
            os.system("ifconfig %s down" % self.interface)
            os.system("iw dev %s set type managed" % self.interface)
            os.system("ifconfig %s up" % self.interface)

            if self.is_ath10k:
                self.cmd_background()
            else:
                self.cmd_chanscan()

        elif self.mode.value == 2:
            print "enter 'background' mode: set dev type to 'monitor'"
            os.system("ifconfig %s down" % self.interface)
            os.system("iw dev %s set type monitor" % self.interface)
            os.system("ifconfig %s up" % self.interface)
            self.cmd_setchannel()
            self.cmd_background()
            self.cmd_trigger()
        else:
            print "unknown mode '%d'" % self.mode.value
            exit(0)

    def _scan(self):
        while True:
            if self.is_ath10k:
                self.cmd_trigger()

            if self.mode.value == 1:  # only in 'chanscan' mode
                cmd = 'iw dev %s scan' % self.interface
                if self.freqlist:
                    cmd = '%s freq %s' % (cmd, ' '.join(self.freqlist))
                os.system('%s >/dev/null 2>/dev/null' % cmd)
            time.sleep(.01)

    def __init__(self, interface, freqlist=None):
        self.interface = interface
        self.freqlist = freqlist
        self.debugfs_dir = self._find_debugfs_dir()
        if not self.debugfs_dir:
            raise Exception, \
                  'Unable to access spectral_scan_ctl file for interface %s' % interface

        self.is_ath10k = self.debugfs_dir.endswith("ath10k")
        self.ctl_file = '%s/spectral_scan_ctl' % self.debugfs_dir
        self.sample_count_file = '%s/spectral_count' % self.debugfs_dir
        self.cur_chan = 6
        self.sample_count = 8
        self.mode = Value('i', 1)  # mode 1 = 'chanscan', mode 2 = 'background scan'
        self.channel_mode = "HT20"
        self.process = Process(target=self._scan, args=())

    def mode_chanscan(self):
        self.mode.value = 1
        self._start_collection()

    def mode_background(self):
        self.mode.value = 2
        self._start_collection()

    def retune_up(self):  # FIXME: not save for 5Ghz / ath10k
        if self.mode.value == 1:  # tuning not possible in mode 'chanscan'
            return
        self.cur_chan += 1
        if self.cur_chan == 14:
            self.cur_chan = 1
        print "tune to channel %d" % self.cur_chan
        self.fix_ht40_mode()
        self.cmd_setchannel()
        self.cmd_trigger()

    def retune_down(self):  # FIXME: not save for 5Ghz / ath10k
        if self.mode.value == 1:  # tuning not possible in mode 'chanscan'
            return
        self.cur_chan -= 1
        if self.cur_chan == 0:
            self.cur_chan = 13
        print "tune to channel %d" % self.cur_chan
        self.fix_ht40_mode()
        self.cmd_setchannel()
        self.cmd_trigger()

    def cmd_samplecount_up(self):
        self.sample_count *= 2
        if self.sample_count == 256:  # special case, 256 is not valid, set to last valid value
            self.sample_count = 255
        if self.sample_count > 255:
            self.sample_count = 1
        self.cmd_set_samplecount(self.sample_count)

    def cmd_samplecount_down(self):
        if self.sample_count == 255:
            self.sample_count = 256  # undo special case, see above
        self.sample_count /= 2
        if self.sample_count < 1:
            self.sample_count = 255
        self.cmd_set_samplecount(self.sample_count)

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

    def cmd_disable(self):
        f = open(self.ctl_file, 'w')
        f.write("disable")
        f.close()

    def cmd_set_samplecount(self, count):
        print "set sample count to %d" % count
        f = open(self.sample_count_file, 'w')
        f.write("%s" % count)
        f.close()

    def cmd_setchannel(self):
        print "set channel to %d in mode %s" % (self.cur_chan, self.channel_mode)
        os.system("iw dev %s set channel %d %s" % (self.interface, self.cur_chan, self.channel_mode))

    def fix_ht40_mode(self):
        if self.channel_mode != "HT20":
            # see https://wireless.wiki.kernel.org/en/developers/regulatory/processing_rules#mhz_channels1
            if self.cur_chan < 8:
                self.channel_mode = "HT40+"
            else:
                self.channel_mode = "HT40-"

    def cmd_toggle_HTMode(self):
        if self.channel_mode == "HT40+" or self.channel_mode == "HT40-":
             self.channel_mode = "HT20"
        else: # see https://wireless.wiki.kernel.org/en/developers/regulatory/processing_rules#mhz_channels1
            if self.cur_chan < 8:
                self.channel_mode = "HT40+"
            else:
                self.channel_mode = "HT40-"
        self.cmd_setchannel()
        self.cmd_trigger()


    def start(self):
        self._start_collection()
        self.process.start()

    def stop(self):
        if self.channel_mode != "HT20":
            self.cmd_toggle_HTMode()
        self.cmd_set_samplecount(8)
        self.cmd_disable()
        self.process.terminate()
        self.process.join()

    def get_debugfs_dir(self):
        return self.debugfs_dir
