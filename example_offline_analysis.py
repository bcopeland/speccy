from spectrum_file import SpectrumFileReader
import cPickle
import os


def process(fn):
    print "processing '%s':" % fn
    f = open(fn, 'r')
    while True:
        try:
            device_id, ts, sample_data = cPickle.load(f)
            for tsf, freq, noise, rssi, pwrs in SpectrumFileReader.decode(sample_data):
                print device_id, ts, tsf, freq, noise, rssi
                for carrier_freq, pwr_level in pwrs.iteritems():
                    print carrier_freq, pwr_level
        except EOFError:
            break


# open all .bin files and process content
def main():
    for fn in os.listdir("./spectral_data"):
        if fn.endswith(".bin"):
            process("./spectral_data/"+fn)

if __name__ == '__main__':
    main()
