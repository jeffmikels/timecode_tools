#!/usr/bin/env python3

import click, mido, time

from timecode import Timecode

def print_message(message):
	print (message)

def listen(port_name):
	port = mido.open_input(port_name)
	# port.callback = print_message
	print('Listening to MIDI messages on > {} <'.format(port_name))
	while 1:
		msg = port.receive(block=True)
		print(f'{time.time()}: {msg}')

@click.command()
@click.option('--port', '-p', help='name of MIDI port to connect to')
def main(port):
	if (port is None):
		print ('Available MIDI ports')
		print (mido.get_output_names())
	else:
		listen(port)
		

main()