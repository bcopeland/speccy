from spectrum_file import SpectrumFileReader
from scanner import Scanner
import sys
import Queue
from datetime import datetime, timedelta
import time

class AthBenchmark(object):

    def __init__(self, iface):
        self.scanner = Scanner(iface)
        fn = '%s/spectral_scan0' % self.scanner.get_debugfs_dir()
        self.file_reader = SpectrumFileReader(fn)
        self.interface = iface

    def get_samples(self, duration):
        sps = 0
        end = datetime.now() + timedelta(seconds=duration)
        while datetime.now() < end:
            try:
                ts, samples = self.file_reader.sample_queue.get(timeout=0.1)
            except Queue.Empty:
                continue
            sps += len(samples) / (17 + 56)  # (header + payload in HT20)
        print "total: %d sps" % sps
        sps /= float(duration)
        return sps

    # count samples in chanscan
    def benchmark_chanscan(self, duration=5, samplecount=8):
        print "\nrun benchmark chanscan with samplecount=%d, duration=%d " % (samplecount, duration)
        self.scanner.cmd_set_samplecount(samplecount)
        self.scanner.mode_chanscan()
        self.scanner.start()
        sps = self.get_samples(duration=duration)
        self.scanner.stop()
        self.file_reader.flush()
        print "%.2f sps, chanscan" % sps
        return sps

    # count samples in bg mode (w/o) load
    def benchmark_background(self, duration=5):
        print "\nrun benchmark background with duration=%d " % duration
        self.scanner.mode_noninvasive_background()
        self.scanner.dev_add_monitor()
        self.scanner.start()
        sps = self.get_samples(duration=duration)
        self.scanner.stop()
        self.file_reader.flush()
        print "%.2f sps, background scan " % sps
        return sps

    def benchmark_manual(self, samplecount=127):
        print "\nrun benchmark manual with samplecount=%d " % samplecount
        self.scanner.mode_manual()
        self.scanner.cmd_manual()
        self.scanner.cmd_set_samplecount(samplecount)
        self.scanner.dev_add_monitor()
        self.scanner.cmd_trigger()
        sps = 0
        reread = 3
        while reread:
            try:
                ts, samples = self.file_reader.sample_queue.get(timeout=0.1)
                sps += len(samples) / (17 + 56)  # (header + payload in HT20)
            except Queue.Empty:
                pass
            reread -= 1
        self.scanner.stop()
        self.file_reader.flush()
        print "got %d samples in manual mode" % sps
        return sps

    def main(self):
        samplecount = [1, 10, 50, 100, 150, 200, 255]
        for sc in samplecount:
            sps = self.benchmark_chanscan( duration=5, samplecount=sc)
            print "sps / samplecount: %.2f" % (sps / sc)
            time.sleep(0.2)

        self.benchmark_background(duration=5)
        time.sleep(0.2)

        self.benchmark_manual(samplecount=127)
        time.sleep(0.2)

        self.cleanup()

    def cleanup(self):
        # self.scanner.stop()
        self.file_reader.stop()


if __name__ == '__main__':
    AthBenchmark(sys.argv[1]).main()
