#!/usr/bin/python
import struct
import sys
import math

def open(path):
    return SpectrumFile(path)

class SpectrumFile(object):

    def __init__(self, path):
        self.fp = file(path)
        self.buf = ""

    def read(self):
        """
        Return all of the available samples, as a set of (tsf, freq, signal)
        pairs.  For partial reads, samples are buffered until available.
        """
        if not self.fp:
            raise ValueError, 'No open file'

        data = self.buf + self.fp.read()

        vals = []
        pos = 0

        pktsize = 3 + 17 + 56
        while pos < len(data) - pktsize + 1:

            (stype, slen) = struct.unpack_from(">BH", data, pos)
            if stype != 1:
                print "Unknown sample type %d" % stype
                break

            pos += 3

            (max_exp, freq, rssi, noise, max_mag, max_index, hweight, tsf) = \
                struct.unpack_from(">BHbbHBBQ", data, pos)
            pos += 17

            sdata = struct.unpack_from("56B", data, pos)
            pos += 56

            sumsq_sample = sum([math.pow(float(x), 2) for x in sdata])
            for i, sample in enumerate(sdata):
                f = freq - (22.0 * 56 / 64.0) / 2 + (22.0 * (i + 0.5)/64.0)
                if sample == 0:
                    sample = 1

                signal = noise + rssi + \
                         20 * math.log10(sample) - 10 * math.log10(sumsq_sample)

                vals.append((tsf, f, signal))

        self.buf = data[pos:]
        return vals
