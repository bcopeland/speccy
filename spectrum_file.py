#!/usr/bin/python
import struct

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

        hdrsize = 3
        while pos < len(data) - hdrsize + 1:

            (stype, slen) = struct.unpack_from(">BH", data, pos)

            # 20 MHz
            if stype == 1:
                pktsize = 17 + 56
                if pos >= len(data) - hdrsize - pktsize + 1:
                    break

                pos += 3
                (max_exp, freq, rssi, noise, max_mag, max_index, hweight, tsf) = \
                    struct.unpack_from(">BHbbHBBQ", data, pos)
                pos += 17

                sdata = struct.unpack_from("56B", data, pos)
                pos += 56
                vals.append((tsf, freq, noise, rssi, sdata))

            # 40 MHz
            elif stype == 2:
                pktsize = 24 + 128
                if pos >= len(data) - hdrsize - pktsize + 1:
                    break

                pos += 3
                (chantype, freq, rssi_l, rssi_u, tsf, noise_l, noise_u,
                 max_mag_l, max_mag_u, max_index_l, max_index_u,
                 hweight_l, hweight_u, max_exp) = \
                    struct.unpack_from(">BHbbQbbHHbbbbb", data, pos)
                pos += 24

                sdata = struct.unpack_from("128B", data, pos)
                pos += 128

                # FIXME send as two halves?
                vals.append((tsf, freq, noise_l, rssi_l, sdata))

            # ath10k
            elif stype == 3:

                pktsize = 26 + 64
                if pos >= len(data) - hdrsize - pktsize + 1:
                    break
                pos += 3
                (chanwidth, freq1, freq2, noise, max_mag, gain_db,
                 base_pwr_db, tsf, max_index, rssi, relpwr_db, avgpwr_db,
                 max_exp) = \
                    struct.unpack_from(">bHHhHHHQBbbbb", data, pos)
                pos += 26

                sdata = struct.unpack_from("64B", data, pos)
                pos += 64
                vals.append((tsf, freq1, noise, rssi, sdata))

            else:
                print "Unknown sample type %d" % stype
                pos += slen


        self.buf = data[pos:]
        return vals
