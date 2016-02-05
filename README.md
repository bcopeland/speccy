## Introduction

This is a simple spectrum visualizer based on the ath9k spectral scan feature.
If you have a Qualcomm/Atheros Wifi device on Linux, and have built the
driver with debugfs support, you can use this program to see the RF spectrum
in something resembling real-time.

![UI](http://bobcopeland.com/images/lj/speccy-anim.gif)

## Prerequisites

 * a device that supports the spectral scan feature (ath9k and ath9k\_htc
   drivers tested at this point)
 * above drivers compiled with debugfs enabled
 * the iw utility installed

## Usage

As root, run:
```
# ./speccy.py wlan0
```
where ```wlan0``` is the device you'd like to use.

## Key bindings

 * 'l' - Toggle line graph
 * 's' - Toggle scatter plot
 * 'c' - Switch scanner to 'chanscan' mode [default]. Hardware tunes to all WiFi channels and deliver a certain number of samples per channel. Default is 8
   * 'Arrow key Up' - Double the number of samples (up to 255)
   * 'Arrow key Down' - Divide the number of samples by two (down to 1)
 * 'b' - Switch scanner to 'background' mode. Hardware will deliver as much samples as possible
   * 'Arrow key Left' - Tune one channel up (only in 'background' mode)
   * 'Arrow key Right' - Tune one channel up (only in 'background' mode)
   * 'Arrow key Up' - Increase the number of samples hold for visualization
   * 'Arrow key Down' - Decrease the number of samples hold for visualization
 * 'm' - Toggle between HT20 [default] and HT40 mode
 * 'd' - Toggle dumping binary data with timestamp in a file
 * 'u' - Toggle UI processing
 * 'q' - Quit the program

## Open issues

 * HT40 decoder seems to produce crap
 * Many features of this software are not tested on 5GHz / ath10k due lack of appropriate hardware
