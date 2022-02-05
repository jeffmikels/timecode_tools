#!/usr/bin/env python3

import click
import mido
import tools

# create a global accumulator for quarter_frames
quarter_frames = [0, 0, 0, 0, 0, 0, 0, 0]


def handle_message(message):
  if message.type == 'quarter_frame':
    quarter_frames[message.frame_type] = message.frame_value
    if message.frame_type == 7:
      tc = tools.mtc_decode_quarter_frames(quarter_frames)
      print('QF:', tc)
  elif message.type == 'sysex':
    # check to see if this is a timecode frame
    if len(message.data) == 8 and message.data[0:4] == (127, 127, 1, 1):
      data = message.data[4:]
      tc = tools.mtc_decode(data)
      print('FF:', tc)
  else:
    print(message)


def listen(port_name):
  port = mido.open_input(port_name)
  # port.callback = print_message
  print('Listening to MIDI messages on > {} <'.format(port_name))
  while 1:
    msg = port.receive(block=True)
    handle_message(msg)


@click.command()
@click.option('--port', '-p', help='name of MIDI port to connect to')
def main(port):
  if (port is None):
    print('Available MIDI ports')
    print(mido.get_input_names())
  else:
    listen(port)


main()
