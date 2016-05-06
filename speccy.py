#!/usr/bin/python
import gi
try:
    gi.require_version('Gtk', '3.0')
except:
    pass
from gi.repository import Gtk, Gdk
from spectrum_file import SpectrumFileReader
import signal
import sys
from math import ceil
import math
from scanner import Scanner
from datetime import datetime
import os
import cPickle


class Speccy(object):
    heatmap = {}
    max_per_freq = {}

    # min freq, max freq (inclusive), ch spacing
    # we will render +/- 10 MHz
    bands = [
        (2412, 2472, 5),        # 2.4 GHz
        (5180, 5240, 20),       # U-NII-1
        (5260, 5320, 20),       # U-NII-2
        (5500, 5580, 20),       # U-NII-2e-a
        (5600, 5700, 20),       # U-NII-2e-b
        (5745, 5825, 20),       # U-NII-3
    ]

    band_idx = 0
    scanners = []
    power_min = -110.0
    power_max = -20.0
    mpf_gen = 0
    mpf_gen_tbl = {}
    hmp_gen = 0
    hmp_gen_tbl = {}
    show_envelope = True
    show_heatmap = True
    lastframe = 0
    redraws = 0
    fps = [0] * 10
    fpsi = 0

    color_map = None
    sf = None
    freq_min = None
    freq_max = None
    last_x = None

    def set_band(self, band_idx):
        band = self.bands[band_idx]
        self.freq_min = band[0] - 10.0
        self.freq_max = band[1] + 10.0
        self.last_x = self.freq_max
        self.band_idx = band_idx
        for scanner in self.scanners:
            scanner.set_freqs(*band)

    def __init__(self, ifaces):
        self.color_map = self.gen_pallete()
        self.scanners = []
        idx = 0
        for iface in ifaces:
            scanner = Scanner(iface, idx=idx)
            scanner.mode_chanscan()
            fn = '%s/spectral_scan0' % scanner.get_debugfs_dir()
            reader = SpectrumFileReader(fn)
            scanner.file_reader = reader
            self.scanners.append(scanner)
            idx += 1
        self.dev_idx = 0  # id of currently selected device
        if not os.path.exists("./spectral_data"):
            os.mkdir("./spectral_data")

        self.set_band(self.band_idx)
        self.dump_to_file = False
        self.dump_file = None
        self.ui_update = True
        self.bg_sample_count = 0
        self.bg_sample_count_limit = 500

    def quit(self, *args):
        Gtk.main_quit()
        self.cleanup()

    def cleanup(self):
        for scanner in self.scanners:
            scanner.stop()
            scanner.file_reader.stop()

    def on_key_press(self, w, event):
        key = Gdk.keyval_name(event.keyval)
        if key == 's':
            self.show_heatmap = not self.show_heatmap
        elif key == 'l':
            self.show_envelope = not self.show_envelope
        elif key == 'q':
            self.quit()
        elif key == 'b':
            self.scanners[self.dev_idx].mode_background()
            self.reset_viewport()
            self.scanners[self.dev_idx].file_reader.flush()
        elif key == 'c':
            self.scanners[self.dev_idx].mode_chanscan()
            self.reset_viewport()
            self.scanners[self.dev_idx].file_reader.flush()
        elif key == 'f':
            # cycle through frequency bands
            idx = (self.band_idx + 1) % len(self.bands)
            self.set_band(idx)
        elif key == 'Left':
            if self.scanners[self.dev_idx].mode.value == 1:  # chanscan
                return
            self.reset_viewport()
            self.scanners[self.dev_idx].retune_down()
            self.scanners[self.dev_idx].file_reader.flush()
        elif key == 'Right':
            if self.scanners[self.dev_idx].mode.value == 1:  # chanscan
                return
            self.reset_viewport()
            self.scanners[self.dev_idx].retune_up()
            self.scanners[self.dev_idx].file_reader.flush()
        elif key == 'Up':
            if self.scanners[self.dev_idx].mode.value == 2:  # background
                self.bg_sample_count_limit += 50
                self.bg_sample_count = 0
                self.reset_viewport()
                print "set bg persistence cnt to %d" % self.bg_sample_count_limit
            else:
                self.scanners[self.dev_idx].cmd_samplecount_up()
        elif key == 'Down':
            if self.scanners[self.dev_idx].mode.value == 2: # background
                self.bg_sample_count_limit -= 50
                if self.bg_sample_count_limit < 0:
                    self.bg_sample_count_limit = 0
                self.bg_sample_count = 0
                self.reset_viewport()
                print "set bg persistence cnt to %d" % self.bg_sample_count_limit
            else:
                self.scanners[self.dev_idx].cmd_samplecount_down()
        elif key == 'd':
            if self.dump_to_file:
                self.dump_to_file = False
                self.dump_file.close()
                print "dump to file finished"
            else:
                fn = "./spectral_data/%s.bin" % datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                print "start dumping to %s" % fn
                self.dump_file = open(fn, 'w')
                self.dump_to_file = True
        elif key == 'u':
            self.ui_update = not self.ui_update
        elif key == 'm':
            self.reset_viewport()
            self.scanners[self.dev_idx].cmd_toggle_HTMode()
            self.scanners[self.dev_idx].file_reader.flush()
        elif key == '1' or key == '2' or key == '3' or key == '4':
            self.dev_idx = int(key) - 1

        else:
            pass  # ignore unknown key

    def gen_pallete(self):
        # create a 256-color gradient from blue->green->white
        start_col = (0.1, 0.1, 1.0)
        mid_col = (0.1, 1.0, 0.1)
        end_col = (1.0, 1.0, 1.0)

        colors = [0] * 256
        for i in range(0, 256):
            if i < 128:
                sf = (128.0 - i) / 128.0
                sf2 = i / 128.0
                colors[i] = (start_col[0] * sf + mid_col[0] * sf2,
                            start_col[1] * sf + mid_col[1] * sf2,
                            start_col[2] * sf + mid_col[2] * sf2)
            else:
                sf = (256.0 - i) / 128.0
                sf2 = (i - 128.0) / 128.0
                colors[i] = (mid_col[0] * sf + end_col[0] * sf2,
                            mid_col[1] * sf + end_col[1] * sf2,
                            mid_col[2] * sf + end_col[2] * sf2)
        return colors

    def sample_to_viewport(self, freq, power, wx, wy):

        # normalize both frequency and power to [0,1] interval, and
        # then scale by window size
        freq_normalized = (freq - self.freq_min) / (self.freq_max - self.freq_min)
        freq_scaled = freq_normalized * wx

        power_normalized = (power - self.power_min) / (self.power_max - self.power_min)
        power_scaled = power_normalized * wy

        # flip origin to bottom left for y-axis
        power_scaled = wy - power_scaled

        return (freq_scaled, power_scaled)

    def draw_centered_text(self, cr, text, x, y):
        x_bearing, y_bearing, width, height = cr.text_extents(text)[:4]
        cr.move_to(x - width / 2 - x_bearing, y - height / 2 - y_bearing)
        cr.show_text(text)

    def draw_grid(self, cr, wx, wy):
        # clear the viewport with a black rectangle
        cr.rectangle(0, 0, wx, wy)
        cr.set_source_rgb(0, 0, 0)
        cr.fill()

        cr.set_source_rgb(1, 1, 1)
        cr.set_line_width(0.5)
        cr.set_dash([2.0, 2.0])
        for freq in range(int(self.freq_min), int(self.freq_max), 5):
            sx, sy = self.sample_to_viewport(freq, self.power_min, wx, wy)
            ex, ey = self.sample_to_viewport(freq, self.power_max, wx, wy)
            cr.move_to(sx, sy)
            cr.line_to(ex, ey)
            cr.stroke()

            if freq != self.freq_min and freq != self.freq_max:
                self.draw_centered_text(cr, "%d" % freq, ex, ey + 30)

        for power in range(int(self.power_min), int(self.power_max), 10):
            sx, sy = self.sample_to_viewport(self.freq_min, power, wx, wy)
            ex, ey = self.sample_to_viewport(self.freq_max, power, wx, wy)
            cr.move_to(sx, sy)
            cr.line_to(ex, ey)
            cr.stroke()

            if power != self.power_min and power != self.power_max:
                self.draw_centered_text(cr, "%d dBm" % power, sx + 30, ey)

        cr.set_dash([])

    def reset_viewport(self):
        self.heatmap = {}
        self.max_per_freq = {}

    def smooth_data(self, vals, window_len):
        smoothed = [self.power_min] * len(vals)
        half_window = window_len / 2
        for i in range(half_window, len(vals) - half_window):
            window = vals[i - half_window:i+half_window]
            smoothed[i] = sum(window) / float(len(window))
        return smoothed

    def update_data(self, w, frame_clock, user_data):

        time = frame_clock.get_frame_time()
        if time - self.lastframe > 1000:
            self.lastframe = time
        else:
            return True

        hmp = self.heatmap
        mpf = self.max_per_freq

        for scanner in self.scanners:
            if scanner.file_reader.sample_queue.empty():
                continue

            ts, xydata = scanner.file_reader.sample_queue.get()
            if self.dump_to_file:
                cPickle.dump((scanner.idx, ts, xydata), self.dump_file)

            if not self.ui_update:
                continue

            for (tsf, freq_cf, noise, rssi, pwr) in SpectrumFileReader.decode(xydata):
                if scanner.mode.value == 1 and freq_cf < self.last_x:  # chanscan
                    # we wrapped the scan...
                    self.hmp_gen += 1
                    self.mpf_gen += 1

                if scanner.mode.value == 2:  # background
                    if self.bg_sample_count == self.bg_sample_count_limit:
                        self.bg_sample_count = 0
                        self.hmp_gen += 1
                        self.mpf_gen += 1
                    self.bg_sample_count += 1

                for freq_sc, sigval in pwr.iteritems():
                    if freq_sc not in hmp or self.hmp_gen_tbl.get(freq_sc, 0) < self.hmp_gen:
                        hmp[freq_sc] = {}
                        self.hmp_gen_tbl[freq_sc] = self.hmp_gen

                    arr = hmp[freq_sc]
                    mody = ceil(sigval*2.0)/2.0
                    arr.setdefault(mody, 0)
                    arr[mody] += 1.0

                    mpf.setdefault(freq_sc, 0)
                    if sigval > mpf[freq_sc] or self.mpf_gen_tbl.get(freq_sc, 0) < self.mpf_gen:
                        mpf[freq_sc] = sigval
                        self.mpf_gen_tbl[freq_sc] = self.mpf_gen

                self.last_x = freq_cf

        if not self.ui_update:
            return True

        self.heatmap = hmp
        self.max_per_freq = mpf
        w.queue_draw()
        return True

    def draw(self, w, cr):
        start = datetime.now()
        wx, wy = (w.get_window().get_width(), w.get_window().get_height())
        self.draw_grid(cr, wx, wy)

        # samples
        rect_size = cr.device_to_user_distance(3, 3)

        zmax = 0
        for center_freq in self.heatmap.keys():
            for power, value in self.heatmap[center_freq].iteritems():
                if zmax < value:
                    zmax = self.heatmap[center_freq][power]

        if not zmax:
            zmax = 1

        if self.show_heatmap:
            # collect rectangle centers binned by intensity
            pal_size = len(self.color_map)
            samples = {}
            for center_freq in self.heatmap.keys():
                for power, value in self.heatmap[center_freq].iteritems():
                    # scale x to viewport
                    posx, posy = self.sample_to_viewport(center_freq, power, wx, wy)

                    # don't bother drawing partially off-screen pixels
                    if posx < 0 or posx > wx or posy < 0 or posy > wy:
                        continue

                    intensity = int(pal_size * value  / zmax) & 0xff
                    l = samples.setdefault(intensity, [])
                    l += [(posx, posy)]

            # render all rectangles batched by color
            for intensity, pts in samples.iteritems():
                color = self.color_map[intensity]
                cr.set_source_rgba(color[0], color[1], color[2], .8)
                for xy in pts:
                    cr.rectangle(xy[0]-rect_size[0]/2, xy[1]-rect_size[1]/2, rect_size[0], rect_size[1])
                cr.fill()

        if self.show_envelope and len(self.max_per_freq.keys()) > 0:
            freqs = sorted(self.max_per_freq.keys())
            pow_data = [self.max_per_freq[f] for f in freqs]
            pow_data = self.smooth_data(pow_data, 4)

            x, y = self.sample_to_viewport(freqs[0], pow_data[0], wx, wy)
            cr.set_source_rgb(1, 1, 0)
            cr.move_to(x, y)
            for i, freq in enumerate(freqs[1:]):
                x, y = self.sample_to_viewport(freq, pow_data[i], wx, wy)
                cr.line_to(x, y)
            cr.stroke()

        end = datetime.now()
        elapsed = (end - start).total_seconds()
        self.fps[self.fpsi] = 1/elapsed
        self.fpsi = (self.fpsi + 1) % len(self.fps)
        sys.stderr.write('FPS %f \r' % (sum(self.fps) / len(self.fps)))

    def main(self):

        signal.signal(signal.SIGINT, self.quit)

        w = Gtk.Window()
        w.set_default_size(800, 400)
        a = Gtk.DrawingArea()
        w.add(a)

        a.add_tick_callback(self.update_data, None)

        w.connect('destroy', Gtk.main_quit)
        w.connect("key_press_event", self.on_key_press)
        a.connect('draw', self.draw)

        w.show_all()

        for scanner in self.scanners:
            scanner.start()

        Gtk.main()

        self.cleanup()

if __name__ == '__main__':
    if len(sys.argv) == 1:
        print "\nUsage: \n  $ sudo python speccy.py wlanX [wlanY] [wlanZ] [wlanA]\n"
        exit(0)
    Speccy(sys.argv[1:]).main()
