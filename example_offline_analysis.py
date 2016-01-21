from spectrum_file import SpectrumFileReader
import cPickle
import os


def process(fn):
    print "processing '%s':" % fn
    f = open(fn, 'r')
    while True:
        try:
            ts, sample_data = cPickle.load(f)
            for tsf, freq, noise, rssi, sdata in SpectrumFileReader.decode(sample_data):
                print ts, tsf, freq, noise
        except EOFError:
            break


# open all .bin files and process content
def main():
    for fn in os.listdir("./spectral_data"):
        if fn.endswith(".bin"):
            process("./spectral_data/"+fn)

if __name__ == '__main__':
    main()
