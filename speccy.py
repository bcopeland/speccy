#!/usr/bin/python
from gi.repository import Gtk
import spectrum_file
import sys
from math import ceil

heatmap = {}
fn = sys.argv[1]
max_per_freq = {}

freq_min = 2402.0
freq_max = 2472.0
power_min = -110.0
power_max = -20.0

def gen_pallete():
    # create a 256-color gradient from blue->green->white
    start_col = (0.1, 0.1, 1.0)
    mid_col = (0.1, 1.0, 0.1)
    end_col = (1.0, 0.1, 0.1)

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


lastframe = 0
redraws = 0
sf = spectrum_file.open(fn)

def sample_to_viewport(freq, power, wx, wy):

    # normalize both frequency and power to [0,1] interval, and
    # then scale by window size
    freq_normalized = (freq - freq_min) / (freq_max - freq_min)
    freq_scaled = freq_normalized * wx

    power_normalized = (power - power_min) / (power_max - power_min)
    power_scaled = power_normalized * wy

    # flip origin to bottom left for y-axis
    power_scaled = wy - power_scaled

    return (freq_scaled, power_scaled)

def draw_centered_text(cr, text, x, y):
    x_bearing, y_bearing, width, height = cr.text_extents(text)[:4]
    cr.move_to(x - width / 2 - x_bearing, y - height / 2 - y_bearing)
    cr.show_text(text)

def draw_grid(cr, wx, wy):
    # clear the viewport with a black rectangle
    cr.rectangle(0, 0, wx, wy)
    cr.set_source_rgb(0, 0, 0)
    cr.fill()

    cr.set_source_rgb(1, 1, 1)
    cr.set_line_width(0.5)
    cr.set_dash([2.0, 2.0])
    for freq in range(int(freq_min), int(freq_max), 5):
        sx, sy = sample_to_viewport(freq, power_min, wx, wy)
        ex, ey = sample_to_viewport(freq, power_max, wx, wy)
        cr.move_to(sx, sy)
        cr.line_to(ex, ey)
        cr.stroke()

        if freq != freq_min and freq != freq_max:
            draw_centered_text(cr, "%d" % freq, ex, ey + 30)

    for power in range(int(power_min), int(power_max), 10):
        sx, sy = sample_to_viewport(freq_min, power, wx, wy)
        ex, ey = sample_to_viewport(freq_max, power, wx, wy)
        cr.move_to(sx, sy)
        cr.line_to(ex, ey)
        cr.stroke()

        if power != power_min and power != power_max:
            draw_centered_text(cr, "%d dBm" % power, sx + 30, ey)

    cr.set_dash([])

def update_data(w, frame_clock, fn):
    global max_per_freq, heatmap, lastframe, redraws

    time = frame_clock.get_frame_time()
    if time - lastframe > 1000:
        lastframe = time
    else:
        return True

    xydata = sf.read()
    if not xydata:
        return True

    redraws += 1
    if redraws > 5:
        redraws = 0
        heatmap = {}

    hmp = heatmap

    for tsf, x, y in xydata:
        modx = x
        arr = hmp.setdefault(modx, {})
        mody = ceil(y*2.0)/2.0
        arr.setdefault(mody, 0)
        arr[mody] += 1.0

    mpf = max_per_freq
    for tsf, x, y in xydata:
        cury = max_per_freq.setdefault(x, y)
        if cury < y:
            mpf[x] = y

    heatmap = hmp
    max_per_freq = mpf
    w.queue_draw()
    return True


def draw(w, cr):

    wx, wy = (w.get_window().get_width(), w.get_window().get_height())
    draw_grid(cr, wx, wy)

    # samples
    rect_size = cr.device_to_user_distance(3, 3)

    zmax = 0
    for x in heatmap.keys():
        for y, value in heatmap[x].iteritems():
            if zmax < value:
                zmax = heatmap[x][y]

    if not zmax:
        zmax = 1

    envelope = False
    if not envelope:
        for x in heatmap.keys():
            for y, value in heatmap[x].iteritems():
                # scale x to viewport
                posx, posy = sample_to_viewport(x, y, wx, wy)

                # don't bother drawing partially off-screen pixels
                if posx < 0 or posx > wx or posy < 0 or posy > wy:
                    continue

                color = color_map[int(len(color_map) * value / zmax) & 0xff]
                cr.rectangle(posx-rect_size[0]/2, posy-rect_size[1]/2, rect_size[0], rect_size[1])
                cr.set_source_rgba(color[0], color[1], color[2], .8)
                cr.fill()
    else:
        freqs = sorted(max_per_freq.keys())
        x, y = sample_to_viewport(freqs[0], max_per_freq[freqs[0]], wx, wy)
        cr.set_source_rgb(1, 1, 0)
        cr.move_to(x, y)
        for freq in freqs[1:]:
            x, y = sample_to_viewport(freq, max_per_freq[freq], wx, wy)
            cr.line_to(x, y)
        cr.stroke()

color_map = gen_pallete()
w = Gtk.Window()
w.set_default_size(800, 400)
a = Gtk.DrawingArea()
w.add(a)

a.add_tick_callback(update_data, sys.argv[1])

w.connect('destroy', Gtk.main_quit)
a.connect('draw', draw)

w.show_all()

Gtk.main()
