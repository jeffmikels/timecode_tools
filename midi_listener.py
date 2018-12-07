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
@click.option('--name', '-n', help='name of MIDI port to connect to')
@click.option('--port', '-p', type=int, help='number of MIDI port to connect to, defaults to 0')
def main(port, name):
	ports = mido.get_output_names()
	if (port is None and name is None):
		print ('Available MIDI ports')
		index = -1
		for name in ports:
			index+=1
			print (f'{index} : {name}')
	elif not name is None:
		listen(name)
	else:
		listen(ports[port])
		

main()