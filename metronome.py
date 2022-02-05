#!/usr/bin/env python3

import click
import sounddevice as sd
import soundfile as sf
import numpy
import time
import threading
import tkinter as tk
import random


def prepare_audio(orig_data, channel, channels):
  # put the audio in the correct channel
  # assuming the input signal has the click on channel 1

  audio_data = []
  for sample in orig_data:
    click_sample = sample[0]
    this_sample = []
    for i in range(channels):
      if i == channel - 1:
        this_sample.append(click_sample)
      else:
        this_sample.append(0)
    audio_data.append(this_sample)
    # print(this_sample)
  return numpy.array(audio_data, dtype="int16")


class Metronome:
  def __init__(self, click_file, bpm, audio_device, audio_channel):
    self.click_file = click_file
    self.bpm = bpm
    self.audio_device = audio_device
    self.audio_channel = audio_channel
    self.setup_audio()
    self.muted = False
    self.running = False
    self.pct = 0
    self.odd_beat = True
    self.next_click = 0
    self.last_click = 0
    self.click_count = 0
    self.metronome_thread = None
    self.observer = {}
    self.volume = 50

  def setup_audio(self):
    orig_data, fs = sf.read(self.click_file, dtype='int16', always_2d=True)
    self.audio_data = prepare_audio(orig_data, self.audio_channel, self.audio_device['channels'])

    sd.default.device = self.audio_device['id']
    sd.default.samplerate = fs

  def observe(self, event_name, callback):
    if event_name not in self.observer:
      self.observer[event_name] = []
    self.observer[event_name].append(callback)

  def play_click(self):
    sd.play(self.audio_data)

  def do_click(self):
    if not self.muted:
      self.play_click()
    self.advance_click()

  def advance_click(self):
    # my measurements show that this method of incrementing
    # the 'next_click' does not have any significant drift
    # even after 5000 seconds
    self.last_click = self.next_click
    self.next_click += 60.0/self.bpm
    self.odd_beat = not self.odd_beat
    self.pct = 1
    if 'click' in self.observer:
      for callback in self.observer['click']:
        callback(self)

  def reset(self):
    was_running = self.running
    if was_running:
      self.stop()

    self.setup_audio()
    if was_running:
      self.start()

  def start(self):
    self.running = True
    self.next_click = time.time() + 60.0/self.bpm
    self.odd_beat = True
    self.metronome_thread = threading.Thread(target=self.do_thread)
    self.metronome_thread.start()

  def stop(self):
    self.running = False
    self.metronome_thread.join()

  def toggle_play(self):
    if self.running:
      self.stop()
    else:
      self.start()

  def toggle_mute(self):
    self.muted = not self.muted
    if not self.muted:
      self.next_click = time.time()

  def do_thread(self):
    while self.running:
      now = time.time()

      if now >= self.next_click:
        # print(f'{now - self.next_click}ms late')
        # threading.Thread(target=self.play_click).start()
        self.do_click()
      else:
        self.pct = 1 - (self.next_click - now) / (self.next_click - self.last_click)

      if 'pct' in self.observer:
        for callback in self.observer['pct']:
          callback(self)

      # don't burn all the cpu...
      time.sleep(.0016666)


class MetronomeApp(tk.Frame):
  def __init__(self, master=None, metronome=None):
    super().__init__(master)
    self.width = 640
    self.height = 100
    self.max_bpm = 300
    self.metronome = metronome
    self.taps = []
    self.last_tap = None
    self.presets = []
    for i in range(9):
      self.presets.append({
          'bpm': 120,
          'color': '#{:02x}{:02x}{:02x}'.format(random.randint(0, 128), random.randint(0, 128), 0)
      })
    self.current_preset = 0

    self.master = master
    self.master.title('Metronome')
    self.master.maxsize(self.width, self.height)
    self.master.minsize(self.width, self.height)
    self.master.geometry(f'{self.width}x{self.height}+0+0')
    self.master.bind("<Key>", self.handle_key)
    self.pack(fill=tk.BOTH, expand=1)

    self.create_widgets()

    # self.metronome.observe('click', self.flash)
    self.metronome.start()

  def flash(self, on=True):
    if on:
      self.device_label['bg'] = 'red'
      self.after(10, lambda: self.flash(False))
    else:
      # self.bpmbar['bg'] = self.presets[self.current_preset]['color']
      self.device_label['bg'] = '#000040'

  def handle_tap(self):
    now = time.time()
    if self.last_tap is None:
      self.last_tap = now
      self.taps = []
      return

    diff = now - self.last_tap
    if diff > 2:
      self.last_tap = now
      self.taps = []
      return

    self.last_tap = now
    self.taps.append(diff)
    if len(self.taps) > 10:
      self.taps = self.taps[1:]

    avgdiff = sum(self.taps) / len(self.taps)
    self.set_bpm(round(60.0 / avgdiff))

  def next_device(self):
    global audio_devices
    current_device = self.metronome.audio_device
    next_device_index = 0
    for i in range(len(audio_devices)):
      if audio_devices[i]['id'] == self.metronome.audio_device['id']:
        next_device_index = (i + 1) % len(audio_devices)
        break
    self.metronome.audio_device = audio_devices[next_device_index]
    self.metronome.reset()
    self.update_device_label()

  def prev_device(self):
    global audio_devices
    current_device = self.metronome.audio_device
    prev_device_index = 0
    for i in range(len(audio_devices)):
      if audio_devices[i]['id'] == self.metronome.audio_device['id']:
        prev_device_index = (i + len(audio_devices) - 1) % len(audio_devices)
        break
    self.metronome.audio_device = audio_devices[prev_device_index]
    self.metronome.reset()
    self.update_device_label()

  def inc_channel(self, inc):
    new_channel = self.metronome.audio_channel + inc
    if new_channel < 1 or new_channel > self.metronome.audio_device['channels']:
      return
    self.metronome.audio_channel = new_channel
    self.metronome.reset()
    self.update_device_label()

  def update_device_label(self):
    self.device_label['text'] = f"Audio: {self.metronome.audio_device['name']} ({self.metronome.audio_device['channels']} channels) • Using Channel {self.metronome.audio_channel}"

  def select_preset(self, new_preset):
    # save current bpm
    self.presets[self.current_preset]['bpm'] = self.metronome.bpm
    self.current_preset = new_preset
    preset = self.presets[self.current_preset]
    self.set_bpm(preset['bpm'])
    self.bpmbar['bg'] = preset['color']

  def handle_key(self, event):
    # print(event.keysym)
    if event.keysym == 'space':
      self.toggle_mute()
    elif event.keysym == 't':
      self.handle_tap()
    # if event.keysym == 'Return':
    #   # strange race conditions here... don't use
    #   self.metronome.do_click()
    elif event.keysym == 'Up':
      self.inc_bpm(1)
    elif event.keysym == 'Down':
      self.inc_bpm(-1)
    elif event.keysym == 'Right':
      self.inc_bpm(10)
    elif event.keysym == 'Left':
      self.inc_bpm(-10)
    elif event.keysym == 'Escape' or event.keysym == 'q':
      self.master.destroy()
    elif event.keysym == 'plus' or event.keysym == 'equal':
      self.inc_channel(1)
    elif event.keysym == 'minus' or event.keysym == 'underscore':
      self.inc_channel(-1)
    elif event.keysym == 'greater' or event.keysym == 'period':
      self.next_device()
    elif event.keysym == 'less' or event.keysym == 'comma':
      self.prev_device()
    else:
      try:
        preset_num = int(event.keysym)
        if preset_num > 0:
          self.select_preset(preset_num - 1)
      except ValueError:
        pass

  def create_widgets(self):
    self.status_height = 40

    # bpmbar
    self.bpmbar = tk.Label(self,
                           text=str(self.metronome.bpm),
                           fg='white',
                           bg=self.presets[self.current_preset]['color'],
                           height=30,
                           )
    self.bpmbar.place(x=0, y=0)
    self.inc_bpm(0)

    # # pendulum
    # self.pendulum = tk.Label(self,
    # 	text='',
    # 	bg='red'
    # )
    # self.pendulum.place(x=0,y=30,width=30,height=30)

    self.device_label = tk.Label(self,
                                 text='',
                                 fg='white',
                                 bg="#000040",
                                 )
    self.device_label.place(x=0, y=30, width=self.width, height=30)
    self.update_device_label()

    self.instructions = tk.Label(self,
                                 #text='[enter] force beat • [space] mutes audio • [t] tap tempo • [up/down right/left] adjust bpm\n[tab] change audio device • [+ or -] change audio channel • [1-9] switch preset',
                                 text='[space] mutes audio • [t] tap tempo • [up/down right/left] adjust bpm\n[< or >] change audio device • [+ or -] change audio channel • [1-9] switch preset',
                                 fg='white',
                                 bg='black'
                                 )
    self.instructions.place(x=0, y=self.height - self.status_height,
                            width=self.width, height=self.status_height)

    # # buttons
    # self.start_stop_button = tk.Button(self)
    # self.start_stop_button['text'] = 'START'
    # self.start_stop_button['command'] = self.toggle_metronome
    # self.start_stop_button.place(x=70, y=10, width=100, height=40)

    # self.mute_button = tk.Button(self)
    # self.mute_button['text'] = 'MUTE'
    # self.mute_button['command'] = self.toggle_mute
    # self.mute_button.place(x=190, y=self.height, width=100, height=40)

    # self.quit_button = tk.Button(self)
    # self.quit_button['text'] = 'QUIT'
    # self.quit_button['command'] = self.master.destroy
    # self.quit_button.place(x=310, y=10, width=100, height=40)

  # def update_pendulum(self, _):
  # 	pendulum_pct = self.metronome.pct
  # 	if self.metronome.odd_beat:
  # 		pendulum_pct = 1 - pendulum_pct
  # 	pendulum_loc = (self.width - 30) * pendulum_pct
  # 	self.pendulum.place(x=pendulum_loc, y=30)

  def toggle_metronome(self):
    self.metronome.toggle_play()

  def toggle_mute(self):
    self.metronome.toggle_mute()

  def inc_bpm(self, inc):
    new_bpm = max(1, min(self.max_bpm, self.metronome.bpm + inc))
    self.set_bpm(new_bpm)

  def set_bpm(self, bpm):
    self.metronome.bpm = bpm
    bpmbarwidth = int(self.width * self.metronome.bpm / self.max_bpm)
    self.bpmbar['width'] = bpmbarwidth
    self.bpmbar['text'] = f'# {self.current_preset + 1} - {self.metronome.bpm}'
    self.bpmbar.place(
        x=0,
        y=0,
        width=bpmbarwidth,
        height=30,
    )


def my_callback(m):
  print(m.pct)


@click.command()
@click.option('--bpm', '-b',  type=int, default=120, help='metronome bpm')
@click.option('--duration', '-d',   type=int, help='duration in seconds to run the metronome, defaults to infinite')
@click.option('--click_file', '-f', default="click.wav", help='file to use for metronome click')
@click.option('--audio_device', '-a', type=int, help='id of selected audio device')
@click.option('--audio_channel', '-c', default=1, help='selected audio channel')
@click.option('--gui/--no_gui', '-g/-n', default=True, help='use gui or not')
def main(bpm, duration, click_file, audio_device, audio_channel, gui):
  global settings
  global metronome
  global audio_devices
  audio_devices = []
  tmp = sd.query_devices()
  for i in range(len(tmp)):
    device = tmp[i]
    channels = device['max_output_channels']
    if channels > 0:
      audio_devices.append({
          'id': i,
          'name': device['name'],
          'channels': channels
      })

  if not gui and audio_device is None:
    print('You must select an audio device.')
    print('Possible output devices are:')
    for device in audio_devices:
      print(f' # {device["id"]} -- {device["name"]}, {device["channels"]} channels out')
    exit()

  if audio_device is None:
    audio_device = audio_devices[0]
  else:
    for device in audio_devices:
      if device['id'] == audio_device:
        audio_device = device
        break

  metronome = Metronome(click_file, bpm, audio_device, audio_channel)
  # metronome.observe(my_callback)

  if not gui:
    try:
      metronome.start()
      if duration:
        time.sleep(duration)
        metronome.stop()
    except KeyboardInterrupt:
      metronome.stop()
      self.metronome_thread.join()

  else:

    root = tk.Tk()
    app = MetronomeApp(master=root, metronome=metronome)
    app.mainloop()
    metronome.stop()

  # metronome(duration, click_file, bpm, audio_device, audio_channel)


main()
