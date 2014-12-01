#!/usr/bin/python
import struct
import sys
import math

def read(f):
    data = f.read()

    vals = []
    pos = 0
    while pos < len(data):
        (stype, slen) = struct.unpack_from(">BH", data, pos)
        if stype != 1:
            print "Unknown sample type %d" % stype
            sys.exit(1)

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

            print "TSF: %d Freq: %d Noise: %d Rssi: %d Signal: %f" % (
                   tsf, f, noise, rssi, signal)

            vals.append((f, signal))

    return vals
