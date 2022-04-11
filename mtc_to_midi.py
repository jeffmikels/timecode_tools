#!/usr/bin/env python3
'''
This script will listen to MTC over a MIDI port and record/execute MIDI commands
based on a configuration file.

The configuration file looks like this:

# this is a comment
01:10:04:21 90,37,56 # -> note_on channel=0 note=55 velocity=86 time=0
01:10:05:01 90,37,00 # -> note_on channel=0 note=55 velocity=0 time=0
01:10:06:23 B0,01,79 # -> control_change channel=0 control=1 value=121 time=0
01:10:06:23 B0,01,75 everything after the three bytes will be ignored
01:10:06:23 B0,01,72 # -> control_change channel=0 control=1 value=114 time=0
01:10:06:23 B0,01,70 # -> control_change channel=0 control=1 value=112 time=0
01:10:07:01 B0,01,6D # -> control_change channel=0 control=1 value=109 time=0

Comment lines begin with a `#` symbol and are ignored by the parser
Blank lines (whitespace only) will also be ignored by the parser
Event lines consist of of a timecode followed by three hex bytes for the midi command
The hex bytes may be followed by a space and an optional comment or a newline character
Everything following the hex bytes will be ignored
Timecode must be in HH:MM:SS:FF format (FF means frames)

'''

import os
from time import sleep, time
import click
import mido
import tools
from timecode import Timecode

# create a global accumulator for quarter_frames
quarter_frames = [0, 0, 0, 0, 0, 0, 0, 0]

# create global timecode object
tc = Timecode(framerate=24, frames=1)
tc_ts = time()
msg_log = []

mtc = None
midi = None


def save(config_file):
  with open(config_file, 'w') as f:
    f.write('\n'.join(msg_log))


class Event:
  def __init__(self, timecode, message):
    self.tc = timecode
    self.msg = message


def update_timecode(message):
  global tc  # because we reassign it here
  global tc_ts  # because we reassign it here
  if message.type == 'quarter_frame':
    quarter_frames[message.frame_type] = message.frame_value
    if message.frame_type == 7:
      tc = tools.mtc_decode_quarter_frames(quarter_frames)
      tc_ts = time()
      # print('QF:', tc)
  elif message.type == 'sysex':
    # check to see if this is a timecode frame
    if len(message.data) == 8 and message.data[0:4] == (127, 127, 1, 1):
      data = message.data[4:]
      tc = tools.mtc_decode(data)
      tc_ts = time()
      # print('FF:', tc)


last_line_length = 0


def status(s):
  global last_line_length
  print('\r' + (' ' * last_line_length) + '\r' + s + ' ', end='')
  last_line_length = len(s) + 1


# switch to callback method!
# based on https://mido.readthedocs.io/en/latest/ports.html#callbacks
def listen(mtc_port, midi_port, config, record_mode):
  global mtc, midi

  # port.callback = print_message
  verb = 'record' if record_mode else 'playback'
  print(f'''
MTC -> MIDI ({verb})
  MTC on [{mtc_port}]
  MIDI on [{midi_port}]
  config file: [{config}]
  
STOP with ^C (Ctrl+C)\n\n''')

  mtc = mido.open_input(mtc_port, autoreset=True)
  old_tc = tc
  events = []
  event_cursor = 0
  next_event = None
  midi = None

  # prepare main midi port
  if mtc_port != midi_port:
    if record_mode:
      midi = mido.open_input(midi_port, autoreset=True)
    else:
      midi = mido.open_output(midi_port, autoreset=True)

  if not record_mode:
    # parse the config file
    events = []
    with open(config, 'r') as f:
      for line in f.readlines():
        line = line.strip()
        if line == '':
          continue
        if line[0] == '#':
          continue

        # everything after the bytes is ignored
        results = line.split(' ', 2)
        if len(results) < 2:
          print(f'IGNORING invalid configuration line: {line}')
          print('\tline should be in this format: HH:MM:SS:FF B1,B2,B3')
          continue
        event_tc = results[0]
        event_hex = results[1]
        try:
          event_msg = mido.Message.from_hex(event_hex, sep=',')
          events.append(Event(event_tc, event_msg))
        except ValueError:
          print(f'IGNORING invalid configuration line: {line}')
          print('\tcould not be parsed into a MIDI command')

    if len(events) == 0:
      print(f'No events found in configuration file: {config}')
      return
    else:
      first_tc = events[0].tc
      last_tc = events[-1].tc
      print(f'Processed: {config}')
      print(f'Found {len(events)} MIDI events in range {first_tc} - {last_tc}')
      print()

  # start main mtc loop
  while 1:
    # update the timecode as soon as possible
    # by grabbing mtc events first
    mtc_msg = mtc.poll()
    if mtc_msg is not None:
      update_timecode(mtc_msg)
      if old_tc != tc:
        line = f'{tc}'

        # going back in time should reset events
        if old_tc > tc:
          print('\n-- TIME WENT BACKWARD --')
          next_event = None

        # if there is no upcoming event, compute one now
        if next_event is None:
          for i, event in enumerate(events):
            if event.tc > tc:
              next_event = event
              event_cursor = i
              break  # this inner for loop

        if next_event is not None:
          line += f' NEXT EVENT: {next_event.tc} -> {next_event.msg}'
        elif not record_mode:
          line += ' NO UPCOMING EVENTS... still listening in case the timeline resets.'

        status(line)
        old_tc = tc

    # make sure we understand the real absolute time right now because
    # we want our events to be as accurate as possible, and the timecode
    # might not show up as frequently as we would like
    now = time()
    elapsed = now - tc_ts  # time since the last timecode was received

    # if the timecode has been stopped longer than one second
    # assume it is really stopped and ignore the "corrected" time
    if elapsed > 1:
      tc_now = tc
    else:
      additional_frames = round(elapsed / 24)
      tc_now = tc + additional_frames  # Timecode class overrides the `+` operator

    # now that we know what time it is, do the other MIDI stuff
    if record_mode:
      # try to grab recordable events from the midi port
      # or use the event we already received from the mtc port
      # (one port can do both jobs)
      if midi is None:
        midi_msg = mtc_msg
      else:
        midi_msg = midi.poll()
      if midi_msg is not None:
        if midi_msg.type != 'sysex' and midi_msg.type != 'quarter_frame':
          comment = f'-> {midi_msg}'
          h = midi_msg.hex(sep=",")
          line = f'{tc_now} {h} # {comment}'
          msg_log.append(line)
          status(line)
          print()
          if (len(msg_log) % 10) == 9:
            save(config)

    else:
      # send pre-recorded MIDI events
      while next_event is not None and tc_now > next_event.tc:
        midi_msg = next_event.msg
        midi.send(midi_msg)
        line = f'{tc} {midi_msg.hex()}'
        status(line)
        print()

        event_cursor += 1
        if event_cursor < len(events):
          next_event = events[event_cursor]
        else:
          next_event = None
          # print('Finished sending all events.')
          # return

    # give the CPU just a bit of a rest
    sleep(0.0001)


def quit():
  if mtc is not None:
    mtc.close()
  if midi is not None:
    midi.close()
  exit()


@click.command()
@click.option('-p', '--midi', help='name of MIDI port to communicate with')
@click.option('-m', '--mtc', help='name of the MIDI port with MTC, defaults to same as midi')
@click.option('-r', '--record', default=False, is_flag=True, help='sets record mode, defaults to off')
@click.option('-l', '--list-ports', is_flag=True, help='lists the available MIDI ports')
@click.option('-c', '--config', default='events.mtc2midi', help='the configuration file to use for storing/reading MIDI events')
def main(mtc, midi, config, record, list_ports):
  """This script will listen to MTC over a MIDI port and record/execute MIDI commands
based on a configuration file.

Open the source code to see an example of a configuration file.
  """
  if list_ports or midi is None:
    print('---------------------')
    print('Available INPUT ports')
    print('---------------------')
    ports = []
    for name in mido.get_input_names():
      if name not in ports:
        ports.append(name)
    for port in ports:
      print(port)

    print('---------------------')
    print('Available OUTPUT ports')
    print('---------------------')
    ports = []
    for name in mido.get_output_names():
      if name not in ports:
        ports.append(name)
    for port in ports:
      print(port)
    exit()

  if mtc is None:
    mtc = midi

  if record and os.path.exists(config):
    confirm = input(f'FILE EXISTS: {config}\nOverwrite? [y/N] ')
    if confirm.lower() != 'y':
      print('Aborted')
      exit()

  if not record and not os.path.exists(config):
    print('Configuration file not found. Aborting.')
    exit()

  try:
    listen(mtc, midi, config, record_mode=record)
    print()
    quit()
  except KeyboardInterrupt:
    if len(msg_log) > 0:
      save(config)
    print()
    quit()


main()
