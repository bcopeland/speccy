#!/usr/bin/python
from gi.repository import Gtk
import spectrum_file
import sys

wx=800
wy=800
heatmap = {}
scale=300.0
fn = sys.argv[1]
max_per_freq = {}

def gen_pallete():
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


lastframe = 0
def update_data(w, frame_clock, fn):
    global max_per_freq, heatmap, lastframe

    time = frame_clock.get_frame_time()
    if time - lastframe > 1000:
        lastframe = time
    else:
        return True

    hmp = heatmap
    try:
        xydata = spectrum_file.read(open(fn))
    except:
        xydata = []
    if not xydata:
        return True

    for x, y in xydata:
        modx = x
        arr = hmp.setdefault(modx, {})
        mody = int((y / -150.0) * scale)
        arr.setdefault(mody, 0)
        arr[mody] += 1.0

    mpf = max_per_freq
    for x, y in xydata:
        cury = max_per_freq.setdefault(x, y)
        if cury < y:
            mpf[x] = y

    heatmap = hmp
    max_per_freq = mpf
    w.queue_draw()
    return True


def draw(w, cr):

    # clear the viewport with a black rectangle
    cr.rectangle(0, 0, wx, wy)
    cr.set_source_rgb(0, 0, 0)
    cr.fill()

    print 'heatmap len %d' % len(heatmap)

    # samples
    rect_size = cr.device_to_user_distance(5, 5)

    zmax = 0
    for x in heatmap.keys():
        for y, value in heatmap[x].iteritems():
            if zmax < value:
                zmax = heatmap[x][y]

    if not zmax:
        zmax = 1

    for x in heatmap.keys():
        for y, value in heatmap[x].iteritems():
            # scale x to viewport
            posx = (x - 2400.0) / (2480.0-2400.0) * wx
            posy = y / scale * wy

            color = color_map[int(len(color_map) * value / zmax) & 0xff]
            cr.rectangle(posx-rect_size[0]/2, posy-rect_size[1]/2, rect_size[0], rect_size[1])
            cr.set_source_rgba(color[0], color[1], color[2], .8)
            cr.fill()

color_map = gen_pallete()
w = Gtk.Window()
w.set_default_size(800, 800)
a = Gtk.DrawingArea()
w.add(a)

a.add_tick_callback(update_data, sys.argv[1])

w.connect('destroy', Gtk.main_quit)
a.connect('draw', draw)

w.show_all()

Gtk.main()
