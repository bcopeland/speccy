#!/usr/bin/python
import struct
import time
import threading
import math
from Queue import Queue
from datetime import datetime


class SpectrumFileReader(object):

    def __init__(self, path):
        self.fp = file(path)
        if not self.fp:
            print "Cant open file '%s'" % path
            raise
        self.sample_queue = Queue()
        self.reader_thread = threading.Thread(target=self.read_samples_thread, args=())
        self.reader_thread_stop = False
        self.reader_thread_pause = False
        self.reader_thread.start()

    def stop(self):
        self.reader_thread_stop = True
        self.reader_thread.join()
        self.flush()

    def flush(self):  # flush queue and empty file / debugfs buffer (dirty)
        self.reader_thread_pause = True
        while not self.sample_queue.empty():
            self.sample_queue.get()
        self.fp.read()
        self.reader_thread_pause = False

    def read_samples_thread(self):
        while not self.reader_thread_stop:
            if self.reader_thread_pause:
                continue
            ts = datetime.now()
            data = self.fp.read()
            if not data:
                time.sleep(.05)
                continue
            self.sample_queue.put((ts, data))

    # spectral scan packet format constants
    hdrsize = 3
    type1_pktsize = 17 + 56
    type2_pktsize = 24 + 128
    type3_pktsize = 26 + 64

    # ieee 802.11 constants
    sc_wide = 0.3125 # in MHz

    @staticmethod
    def decode(data):
        """
        For information about the decoding of spectral samples see:
        https://wireless.wiki.kernel.org/en/users/drivers/ath9k/spectral_scan
        https://github.com/erikarn/ath_radar_stuff/tree/master/lib
        and your ath9k implementation in e.g.
        /drivers/net/wireless/ath/ath9k/common-spectral.c
        """
        pos = 0
        while pos < len(data) - SpectrumFileReader.hdrsize + 1:

            (stype, slen) = struct.unpack_from(">BH", data, pos)

            if not ((stype == 1 and slen == SpectrumFileReader.type1_pktsize) or
                    (stype == 2 and slen == SpectrumFileReader.type2_pktsize) or
                    (stype == 3 and slen == SpectrumFileReader.type3_pktsize)):
                break  # header malformed, discard data. This event is very unlikely (once in ~3h)
                # On the other hand, if we buffer the sample in a primitive way, we consume to much cpu
                # for only one or too "rescued" samples every 2-3 hours

            # 20 MHz
            if stype == 1:
                if pos >= len(data) - SpectrumFileReader.hdrsize - SpectrumFileReader.type1_pktsize + 1:
                    break
                pos += SpectrumFileReader.hdrsize
                (max_exp, freq, rssi, noise, max_mag, max_index, hweight, tsf) = \
                    struct.unpack_from(">BHbbHBBQ", data, pos)
                pos += 17

                sdata = struct.unpack_from("56B", data, pos)
                pos += 56

                # unscale bins + create binsum
                sumsq_sample = 0
                samples = []
                for raw_sample in sdata:
                    sample = raw_sample << max_exp
                    sumsq_sample += sample*sample
                    if sample == 0:
                        sample = 1
                    samples.append(sample)

                if sumsq_sample == 0:
                    sumsq_sample = 1

                # calculate power in dBm
                sc_total = 56  # HT20: 56 ODFM subcarrier, HT40: 128
                first_sc = freq - SpectrumFileReader.sc_wide * (sc_total/2 + 0.5)
                pwr = {}
                for i, sample in enumerate(samples):
                    subcarrier_freq = first_sc + i*SpectrumFileReader.sc_wide
                    sigval = noise + rssi + 20 * math.log10(sample) - 10 * math.log10(sumsq_sample)
                    pwr[subcarrier_freq] = sigval

                yield (tsf, freq, noise, rssi, pwr)


            # 40 MHz
            elif stype == 2:
                if pos >= len(data) - SpectrumFileReader.hdrsize - SpectrumFileReader.type2_pktsize + 1:
                    break
                pos += SpectrumFileReader.hdrsize
                (chantype, freq, rssi_l, rssi_u, tsf, noise_l, noise_u,
                 max_mag_l, max_mag_u, max_index_l, max_index_u,
                 hweight_l, hweight_u, max_exp) = \
                    struct.unpack_from(">BHbbQbbHHbbbbb", data, pos)
                pos += 24

                sdata = struct.unpack_from("128B", data, pos)
                pos += 128

                # FIXME send as two halves?
                yield (tsf, freq, noise_l, rssi_l, sdata)

            # ath10k
            elif stype == 3:
                if pos >= len(data) - SpectrumFileReader.hdrsize - SpectrumFileReader.type3_pktsize + 1:
                    break
                pos += SpectrumFileReader.hdrsize
                (chanwidth, freq1, freq2, noise, max_mag, gain_db,
                 base_pwr_db, tsf, max_index, rssi, relpwr_db, avgpwr_db,
                 max_exp) = \
                    struct.unpack_from(">bHHhHHHQBbbbb", data, pos)
                pos += 26

                sdata = struct.unpack_from("64B", data, pos)
                pos += 64
                yield (tsf, freq1, noise, rssi, sdata)
