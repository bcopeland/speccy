#!/usr/bin/python
from multiprocessing import Value
from threading import Thread, Lock
import os
import time


class Scanner(object):

    interface = None
    freqlist = None
    process = None
    debugfs_dir = None
    is_ath10k = False
    lock = None
    run = True

    def dev_to_phy(self, dev):
        f = open("/sys/class/net/%s/phy80211/name" % dev)
        phy = f.read().strip()
        f.close()
        return phy

    def freq_to_chan(self, freq):
        chan = 0
        if freq >= 2412 and freq <= 2472:
            chan = (freq - 2407) / 5
        if freq >= 5180 and freq <= 5900:
            chan = (freq - 5000) / 5
        return chan

    def _find_debugfs_dir(self):
        """search debugfs for spectral_scan_ctl for this interface"""
        for dirname, subd, files in os.walk("/sys/kernel/debug/ieee80211"):
            if "spectral_scan_ctl" in files:
                phy = dirname.split(os.path.sep)[-2]
                if phy == self.dev_to_phy(self.interface):
                    self.phy = phy
                    return dirname
        return None

    def _scan(self):
        while self.run:
            if self.is_ath10k:
                self.cmd_trigger()

            if self.mode.value == 1:  # only in 'chanscan' mode
                cmd = "iw dev %s scan" % self.interface
                self.lock.acquire()
                if self.freqlist:
                    cmd = "%s freq %s" % (cmd, " ".join(self.freqlist))
                self.lock.release()
                os.system("%s >/dev/null 2>/dev/null" % cmd)
            time.sleep(0.01)

    def __init__(self, interface, idx=0):
        self.interface = interface
        self.lock = Lock()
        self.phy = ""
        self.idx = idx
        self.monitor_name = "ssmon%d" % self.idx  # just a arbitrary, but unique id
        self.monitor_added = False
        self.debugfs_dir = self._find_debugfs_dir()
        if not self.debugfs_dir:
            raise Exception(
                "Unable to access spectral_scan_ctl file for interface %s" % interface
            )

        self.is_ath10k = self.debugfs_dir.endswith("ath10k")
        self.ctl_file = "%s/spectral_scan_ctl" % self.debugfs_dir
        self.sample_count_file = "%s/spectral_count" % self.debugfs_dir
        self.short_repeat_file = "%s/spectral_short_repeat" % self.debugfs_dir
        self.cur_chan = 6
        self.sample_count = 8
        self.mode = Value(
            "i", -1
        )  # -1 = undef, 1 = 'chanscan', 2 = 'background scan', 3 = 'noninvasive bg scan'
        self.channel_mode = "HT20"
        self.thread = None
        self.file_reader = None
        self.noninvasive = False
        self.set_freqs(2412, 2472, 5)

    def set_freqs(self, minf, maxf, spacing):
        self.lock.acquire()
        self.freqlist = ["%s" % x for x in range(minf, maxf + spacing, spacing)]
        self.lock.release()
        # TODO restart scanner
        self.freq_idx = 0
        print("freqlist: %s" % self.freqlist)

    def hw_setup_chanscan(self):
        print("enter 'chanscan' mode: set dev type to 'managed'")
        os.system("ip link set %s down" % self.interface)
        os.system("iw dev %s set type managed" % self.interface)
        os.system("ip link set %s up" % self.interface)
        if self.is_ath10k:
            self.cmd_background()
        else:
            self.cmd_chanscan()

    def hw_setup_background(self):
        if self.noninvasive:
            self.dev_add_monitor()
        else:
            print("enter 'background' mode: set dev type to 'monitor'")
            os.system("ip link set %s down" % self.interface)
            os.system("iw dev %s set type monitor" % self.interface)
            os.system("ip link set %s up" % self.interface)
            self.cmd_setfreq(0)
        self.cmd_background()
        self.cmd_trigger()

    def mode_chanscan(self):
        if self.mode.value != 1:
            self.hw_setup_chanscan()
            self.mode.value = 1

    def mode_background(self):
        if self.mode.value != 2:
            self.hw_setup_background()
            self.mode.value = 2

    def mode_manual(self):
        self.mode.value = 3

    def mode_noninvasive_background(self):
        self.noninvasive = True
        self.mode_background()

    def retune_up(self):  # FIXME: not save for 5Ghz / ath10k
        if self.mode.value == 1:  # tuning not possible in mode 'chanscan'
            return

        idx = (self.freq_idx + 1) % len(self.freqlist)

        print("tune to freq %s" % self.freqlist[idx])
        self.fix_ht40_mode()
        self.cmd_setfreq(idx)
        self.cmd_trigger()

    def retune_down(self):  # FIXME: not save for 5Ghz / ath10k
        if self.mode.value == 1:  # tuning not possible in mode 'chanscan'
            return

        idx = (self.freq_idx - 1) % len(self.freqlist)

        print("tune to freq %s" % self.freqlist[idx])
        self.fix_ht40_mode()
        self.cmd_setfreq(idx)
        self.cmd_trigger()

    def cmd_samplecount_up(self):
        self.sample_count *= 2
        if (
            self.sample_count == 256
        ):  # special case, 256 is not valid, set to last valid value
            self.sample_count = 255
        if self.sample_count > 255:
            self.sample_count = 1
        self.cmd_set_samplecount(self.sample_count)

    def cmd_samplecount_down(self):
        if self.sample_count == 255:
            self.sample_count = 256  # undo special case, see above
        self.sample_count //= 2
        if self.sample_count < 1:
            self.sample_count = 255
        self.cmd_set_samplecount(self.sample_count)

    def cmd_trigger(self):
        f = open(self.ctl_file, "w")
        f.write("trigger")
        f.close()

    def cmd_background(self):
        f = open(self.ctl_file, "w")
        f.write("background")
        if self.is_ath10k:
            f.write("trigger")
        f.close()

    def cmd_manual(self):
        f = open(self.ctl_file, "w")
        f.write("manual")
        f.close()

    def cmd_chanscan(self):
        f = open(self.ctl_file, "w")
        f.write("chanscan")
        f.close()

    def cmd_disable(self):
        f = open(self.ctl_file, "w")
        f.write("disable")
        f.close()

    def cmd_set_samplecount(self, count):
        print("set sample count to %d" % count)
        f = open(self.sample_count_file, "w")
        f.write("%s" % count)
        f.close()

    def set_short_repeat(self, short_repeat):
        f = open(self.short_repeat_file, "w")
        f.write("%s" % short_repeat)
        f.close()

    def cmd_toggle_short_repeat(self):
        f = open(self.short_repeat_file, "r")
        curval = int(f.read())
        f.close()
        if curval == 0:
            curval = 1
        else:
            curval = 0
        print("set short repeat to %d" % curval)
        self.set_short_repeat(curval)

    def cmd_setchannel(self):
        print("set channel to %d in mode %s" % (self.cur_chan, self.channel_mode))
        if not self.noninvasive:
            os.system(
                "iw dev %s set channel %d %s"
                % (self.interface, self.cur_chan, self.channel_mode)
            )
        else:  # this seems to be strange:
            os.system(
                "iw dev %s set channel %d %s"
                % (self.monitor_name, self.cur_chan, self.channel_mode)
            )

    def cmd_setfreq(self, idx):
        freq = self.freqlist[idx]
        chan = self.freq_to_chan(int(freq))
        mode = self.channel_mode
        print("set freq to %s (%d) in mode %s" % (freq, chan, mode))
        if not self.noninvasive:
            os.system("iw dev %s set freq %s %s" % (self.interface, freq, mode))
        else:  # this seems to be strange:
            os.system("iw dev %s set freq %s %s" % (self.monitor_name, freq, mode))
        self.freq_idx = idx

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
        else:  # see https://wireless.wiki.kernel.org/en/developers/regulatory/processing_rules#mhz_channels1
            if self.cur_chan < 8:
                self.channel_mode = "HT40+"
            else:
                self.channel_mode = "HT40-"
        self.cmd_setchannel()
        self.cmd_trigger()

    def dev_add_monitor(self):
        if self.monitor_added:
            return
        print("add a monitor interface")
        os.system(
            "iw phy %s interface add %s type monitor" % (self.phy, self.monitor_name)
        )
        os.system("ip link set %s up" % self.monitor_name)
        self.monitor_added = True

    def dev_del_monitor(self):
        if self.monitor_added:
            os.system("ip link set %s down" % self.monitor_name)
            os.system("iw dev %s del" % self.monitor_name)
            self.monitor_added = False

    def start(self):
        if self.thread is None:
            self.thread = Thread(target=self._scan, args=())
            self.run = True
            self.thread.start()

    def stop(self):
        if self.channel_mode != "HT20":
            self.cmd_toggle_HTMode()
        self.cmd_set_samplecount(8)
        self.cmd_disable()
        self.dev_del_monitor()
        if self.thread is not None:
            self.run = False
            self.thread.join()
            self.thread = None
        self.mode.value = -1

    def get_debugfs_dir(self):
        return self.debugfs_dir
