## Introduction

This is a simple spectrum visualizer based on the ath9k spectral scan feature.
If you have a Qualcomm/Atheros Wifi device on Linux, and have built the
driver with debugfs support, you can use this program to see the RF spectrum
in real-time.

## Usage

```
# echo background > /sys/kernel/debug/ieee80211/phy1/ath9k/spectral_scan_ctl
# while true; do iw dev wlan0 scan > /dev/null; sleep 0.5; done &
# ./speccy.py /sys/kernel/debug/ieee80211/phy1/ath9k/spectral_scan0
```

