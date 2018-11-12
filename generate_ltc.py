#!/usr/bin/env python3

from tools import cint, ltc_encode
from timecode import Timecode
import time, os, click

def write_wave_file(f, data, rate=44100, bits=8):
	header = gen_wave_header(data, rate=rate, bits=bits)
	f.write(header)
	f.write(data)

def gen_wave_header(data, rate=44100, bits=8, channels=1):
	# integers are stored in C format
	# where 0x0000 + 1 = 0x0100 AND 0xFF00 + 1 = 0x0001
	# the following header has a specified length
	header_length = 4+4+4+4+4+2+2+4+4+2+2+4+4
	data_length = len(data)
	file_length = header_length + data_length
	header = b''
	header += b'RIFF'                              # ascii RIFF
	header += cint(file_length,4)                  # file size data
	header += b'WAVE'                              # ascii WAVE
	header += b'fmt '                              # includes trailing space
	header += cint(16,4)                           # length of format data (16)
	header += cint(1,2)                            # type of format (1 is PCM)
	header += cint(channels,2)                     # number of channels
	header += cint(rate,4)                         # 44100 sample rate
	header += cint(rate * bits * channels / 8, 4)  # (sample rate * bits per sample * channels) / 8
	header += cint(bits * channels / 8, 2)         # (bits per sample * channels) / 8
	header += cint(bits,2)                         # bits per sample
	header += b'data'                              # marks the beginning of the data section
	header += cint(data_length,4)                  # size of the data section
	return header

@click.command()
@click.option('--fps', '-f',   default='24', help='frames per second, defaults to 24')
@click.option('--start', '-s', default='00:01:00:00',  help='start timecode, defaults to 00:01:00:00')
@click.option('--duration', '-d',   default='60', help='duration in seconds for the ltc, defaults to 60')
@click.option('--rate', '-r',   default=44100, help='sample rate, defaults to 44100')
@click.option('--bits', '-b',   default=8, help='bits per sample, defaults to 8')
def make_ltc_wave(fps, start, duration, rate, bits):
	fps     = float(fps)
	duration=float(duration)
	max_val = 2**bits - 1  # 2^8 - 1 = 0b11111111

	# each frame has 80 bytes, and each byte is represented by two "notes"
	# to represent a 0, we use FF FF or 00 00
	# to represent a 1, we use FF 00 or 00 FF
	# every double-note must start with the opposite of the previous half note

	# generate the timecode data for the entire duration
	tc = Timecode(fps, start)
	tc_encoded = []
	print('Generating Timecode Stream')
	for i in range(int(duration * fps) + 1):
		# this is the first frame
		e = ltc_encode(tc, as_string=True)
		tc_encoded.append(e)
		tc.next()

	# lists are faster than string concatenation even when joining them at the end
	tc_encoded = ''.join(tc_encoded)

	print('Generating "Double Pulse" Data Stream')
	double_pulse_data = ''
	next_is_up = True
	for byte_char in tc_encoded:
		if byte_char == '0':
			if next_is_up:
				double_pulse_data += '11'
			else:
				double_pulse_data += '00'
			next_is_up = not next_is_up
		else:
			double_pulse_data += '10' if next_is_up else '01'

	# at this point, we have a string of zeroes and ones
	# now, we just need to map them to pulse data over the
	# duration of the data stream
	print('Creating PCM Data Stream')

	total_samples = int(rate * duration)
	data = bytearray(total_samples)
	for sample in range(total_samples):
		ratio = sample/total_samples
		pct = int(ratio * 100)
		if sample % 1000 == 0:
			print(f'   COMPUTING:  {total_samples}:{sample}  --  {pct}%', end='\r')
		# how far along in the bytestream are we?
		# there are 160 double-pulses per frame

		double_pulse_position = len(double_pulse_data) * ratio
		dpp_intpart = int(double_pulse_position)
		this_val = int(double_pulse_data[dpp_intpart])
	
		# # This code was used when I thought I needed to smooth
		# # out the pulses. Turns out that smoothing isn't needed
		# dpp_fracpart = double_pulse_position - dpp_intpart
		# try:
		# 	next_val = int(double_pulse_data[dpp_intpart+1])
		# except:
		# 	next_val = this_val
		# #scale the value
		# if dpp_fracpart < .5:
		# 	dpp_fracpart *= .5
		# else:
		# 	dpp_fracpart += (1 - dpp_fracpart) * .5
		# inc = (next_val - this_val) * dpp_fracpart
		# scaled_val = int((this_val + inc) * max_val)
		# data[sample] = scaled_val
	
		data[sample] = this_val * max_val
	
	print()
	print('Writing WAV File')
	wave_file_name = 'ltc-{}fps-{}secs.wav'.format(fps, duration)
	f = open(wave_file_name, 'wb')
	write_wave_file(f, data, rate=rate, bits=bits)
	f.close()


# def run(fps, realtime=True, duration=None, renderer=print):
# 	tc1 = Timecode(fps, '00:00:00:00')
# 	frame_size = 1/fps
# 	app_start = time.time()
# 	while 1:
# 		if not realtime:
# 			tc1.next()
# 			renderer(tc1)
# 		else:
# 			now_time = time.time() - app_start
#
# 			if now_time > tc1.frame_number * frame_size:
# 				renderer(tc1)
# 				tc1.next()
# 			time.sleep(0.001)
#
# 		if tc1.frame_number * frame_size > duration:
# 			break


make_ltc_wave()