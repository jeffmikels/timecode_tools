#!/usr/bin/env python3

# use click library
# user input:
# 	fps, start, duration, midi_port

import time
import click
import mido
from timecode import Timecode

import tools


def send_click(outport, note):
  msg = mido.Message('note_on', note=note, velocity=127, channel=9)
  outport.send(msg)
  msg = mido.Message('note_off', note=note, velocity=0, channel=9)
  outport.send(msg)


def send_full_frame(outport, timecode):
  full_frame = tools.mtc_full_frame(timecode)
  # print(full_frame)
  msg = mido.Message.from_bytes(full_frame)
  outport.send(msg)


def send_quarter_frames(outport, timecode, part=0):
  if part == 8:
    return
  # print (timecode)
  qframe = tools.mtc_quarter_frame(timecode, part)
  # print(qframe)
  msg = mido.Message.from_bytes(qframe)
  outport.send(msg)
  send_quarter_frames(outport, timecode, part+1)


def start_mtc(outport, fps, start_string, duration, click_data=None):
  tc = Timecode(fps, start_string)
  frametime = 1/float(fps)
  start = time.time()
  end = start + int(duration)
  if duration == 0:
    infinite = True

  runstring = 'forever' if infinite else f'for {duration}s'
  print(f'STARTING MTC: {fps}fps {start_string} - will run {runstring}')
  next_frame_time = start + tc.frame_number * frametime
  next_full_frame_time = start
  next_click_time = start
  do_click = False
  runuptimes = []
  if click_data is not None:
    in_runup = True
    do_click = True
    clicktime = 60 / float(click_data['bpm'])
    click_divs = int(click_data['division'])
    click_bnote = int(click_data['base_note'])
    click_anote = int(click_data['accent_note'])
    if click_divs == 3:
      runuptimes = [start, start+clicktime*2, start+clicktime*3, start+clicktime*5]
      for i in range(6, click_divs + 6):
        runuptimes.append(start + clicktime*i)
    elif click_divs == 4:
      runuptimes = [start, start+clicktime*2]
      for i in range(4, click_divs+4):
        runuptimes.append(start + clicktime * i)
    elif click_divs == 6:
      runuptimes = [start, start+clicktime*3]
      for i in range(6, click_divs+6):
        runuptimes.append(start + clicktime * i)
    else:
      runuptimes = []
      for i in range(click_divs*2):
        runuptimes.append(start + clicktime * i)
    runuptime = runuptimes[-1] + clicktime
    start = runuptime
    next_click_time = runuptime
  click_counter = 0

  while len(runuptimes) > 0:
    now = time.time()
    if now >= runuptimes[0]:
      send_click(outport, click_anote + 12)
      runuptimes = runuptimes[1:]
    else:
      time.sleep(runuptimes[0]-now)

  print('beginning')
  while 1:
    now = time.time()
    if do_click and now >= next_click_time:
      if click_counter % click_divs == 0:
        send_click(outport, click_anote)
      else:
        send_click(outport, click_bnote)
      click_counter += 1
      next_click_time = start + click_counter * clicktime

    # send mtc
    if not infinite and now > end:
      print('ENDING')
      break
    elif now >= next_full_frame_time:
      tc.next()
      send_full_frame(outport, tc)
      next_frame_time = start + tc.frame_number * frametime
      next_full_frame_time = next_frame_time + 10 * frametime
    elif now > next_frame_time:
      tc.next()
      send_quarter_frames(outport, tc)
      next_frame_time = start + tc.frame_number * frametime
    # wait_until = min(next_frame_time, next_click_time, next_full_frame_time)
    # time.sleep(max(0, wait_until - time.time()))
    time.sleep(0.001)


@click.command()
@click.option('--fps', '-f',   default='24', help='frames per second, defaults to 24')
@click.option('--start', '-s', default='00:00:00:00',  help='start timecode, defaults to 00:00:00:00')
@click.option('--duration', '-d',   default='0', help='duration in seconds to run the mtc, defaults to 0 (infinite)')
@click.option('--metronome/--no_metronome', '-m', default=False, help='turn the metronome on (channel 10)')
@click.option('--bpm', help='set metronome bpm')
@click.option('--division', default=4, help='set metronome division (beats per bar)')
@click.option('--base_note', default=36, help='MIDI note of base click')
@click.option('--accent_note', default=60, help='MIDI note of accent click')
@click.option('--port',     '-p',   help='name of MIDI port to connect to')
def main(fps, start, duration, metronome, bpm, division, base_note, accent_note, port):
  if (port is None):
    print('You must specify a port name. (use --help or -h for more info)')
    print('Possible ports are:')
    print(mido.get_output_names())

    exit()

  outport = mido.open_output(port)
  # wants fps as a string
  try:
    if metronome:
      click_data = {
          'bpm': int(bpm),
          'division': division,
          'base_note': base_note,
          'accent_note': accent_note
      }
      start_mtc(outport, fps, start, float(duration), click_data)
    else:
      start_mtc(outport, fps, start, float(duration))
  except:
    print('error somewhere')


main()
