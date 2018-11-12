#!/usr/bin/env python3

#use click library
# user input:
# 	fps, start, duration, midi_port

import time
import click, mido
from timecode import Timecode

import tools

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

def start_mtc(outport, fps, start_string, duration):
	tc = Timecode(fps, start_string)
	frametime = 1/float(fps)
	start = time.time()
	end = start + int(duration)
	next_frame_time = start + tc.frame_number * frametime
	next_full_frame_time = start
	while 1:
		now = time.time()
		if now > end:
			break
		elif now >= next_full_frame_time:
			tc.next()
			send_full_frame(outport, tc)
			next_frame_time = start + tc.frame_number * frametime
			next_full_frame_time = next_frame_time + 10 * frametime
		elif time.time() > next_frame_time:
			tc.next()
			send_quarter_frames(outport, tc)
			next_frame_time = start + tc.frame_number * frametime
		time.sleep(max(0,next_frame_time - time.time()))

@click.command()
@click.option('--fps', '-f',   default='24', help='frames per second, defaults to 24')
@click.option('--start', '-s', default='00:00:00:00',  help='start timecode, defaults to 00:00:00:00')
@click.option('--duration', '-d',   default='60', help='duration in seconds to run the mtc, defaults to 60')
@click.option('--port',     '-p',   help='name of MIDI port to connect to')
def main(fps, start, duration, port):
	if (port is None):
		print ('You must specify a port name.')
		print ('Possible ports are:')
		print (mido.get_output_names())
		exit()
		
	outport = mido.open_output(port)
	outport.send(mido.Message('note_on', note=72))
	#wants fps as a string
	start_mtc(outport, fps, start, float(duration))
	
main()