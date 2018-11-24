#!/usr/bin/env python3

import click
import sounddevice as sd
import soundfile as sf
import time
# import numpy

def metronome(duration, click_file, click_bpm, audio_device, audio_channel):
	orig_data, fs = sf.read(click_file)
	# put the audio in the correct channel
	data = []
	for sample in orig_data:
		this_sample = []
		for i in range(audio_channel-1):
			this_sample.append(0)
		this_sample.append(sample)
		
		# always make sure there are at least two channels
		if len(this_sample) == 1:
			this_sample.append(0)
		data.append(this_sample)
		
	sd.default.device = audio_device
	sd.default.samplerate = fs
	sd.play(data)
	
	start = time.time()
	click_delay = 60/click_bpm
	next_click_time = start
	end_time = start + duration
	first_time = True
	
	to_right = True
	base_throbber = '|                       |'
	throbber_char = '●'
	throbber_from = 1
	throbber_to = len(base_throbber) - 1
	throbber_width = len(base_throbber) - 2
	use_throbber = False
	while 1:
		now = time.time()
		if now > end_time:
			sd.wait()
			print('done')
			break
		
		if use_throbber:
			throbber_pos = max(1, 1 + throbber_width * (next_click_time - now)/click_delay)
			if not to_right:
				throbber_pos = throbber_width - throbber_pos
			throbber = list(base_throbber)
			throbber[round(throbber_pos)] = throbber_char
			print('  ' + ''.join(throbber) + str(throbber_pos), end='\n')
		
		if now >= next_click_time:
			to_right = not to_right
			sd.play(data)
			new_click_time = next_click_time + click_delay
			next_click_time = new_click_time
		sleep_time = next_click_time - now
		# print('sleeping: ' + str(sleep_time))
		# time.sleep(sleep_time)
		time.sleep(0.01)

@click.command()
@click.option('--duration', '-d',   type=int, default=60, help='duration in seconds to run the mtc, defaults to 60')
@click.option('--click_file', '-f', help='file to use for metronome click')
@click.option('--click_bpm', '-b',  type=int, default=120, help='metronome bpm')
@click.option('--audio_device', '-a', type=int, help='selected audio device')
@click.option('--audio_channel', '-c', default=1, help='selected audio channel')
def main(duration, click_file, click_bpm, audio_device, audio_channel):
	if (audio_device is None):
		print ('You must select an audio device.')
		print ('Possible devices are:')
		print (sounddevice.query_devices())
		exit()
	
	metronome(duration, click_file, click_bpm, audio_device, audio_channel)
		
main()