#!/usr/bin/env python3

from timecode import Timecode
import time
import os
from math import sin, pi


def bitstring_to_bytes(s, bytecount=1, byteorder='big'):
	return int(s, 2).to_bytes(bytecount, byteorder)

# binary big-endian
def bbe(n, bits=8):
	# terminal condition
	retval = ''
	if n == 0:
		retval = '0'
	else:
		retval = bbe(n//2, None) + str(n%2)
	if bits is None:
		return retval
	else:
		return (('0'*bits) + retval)[-bits:]
	

# binary, little-endian
def ble(n, bits=8):
	# terminal condition
	retval = ''
	if n == 0:
		retval = '0'
	else:
		retval = str(n%2) + ble(n//2, None)
	if bits is None:
		return retval
	else:
		return (retval + ('0'*bits))[0:bits]

def cint(n, bytecount=2):
	return n.to_bytes(bytecount, byteorder='little')

def units_tens(n):
	return n % 10, int(n/10)

# GENERATE BINARY-CODED DATA FOR LTC
# ACCORDING TO https://en.wikipedia.org/wiki/Linear_timecode
# everything is encoded little endian
# so to encode the number 3 with four bits, we have 1100
def ltc_encode(timecode, as_string=False):
	LTC = ''
	HLP = ''
	hrs, mins, secs, frs = timecode.frames_to_tc(timecode.frames)
	frame_units, frame_tens = units_tens(frs)
	secs_units, secs_tens = units_tens(secs)
	mins_units, mins_tens = units_tens(mins)
	hrs_units, hrs_tens = units_tens(hrs)
	
	#frames units / user bits field 1 / frames tens
	LTC += ble(frame_units,4) + '0000' + ble(frame_tens,2)
	HLP += '---{u}____-{t}'.format(u=frame_units, t=frame_tens)
	
	#drop frame / color frame / user bits field 2
	LTC += '00'+'0000'
	HLP += '__'+'____'
	
	#secs units / user bits field 3 / secs tens
	LTC += ble(secs_units,4) + '0000' + ble(secs_tens,3)
	HLP += '---{u}____--{t}'.format(u=secs_units, t=secs_tens)

	# bit 27 flag / user bits field 4
	LTC += '0' + '0000'
	HLP += '_' + '____'

	#mins units / user bits field 5 / mins tens
	LTC += ble(mins_units,4) + '0000' + ble(mins_tens,3)
	HLP += '---{u}____--{t}'.format(u=mins_units, t=mins_tens)

	# bit 43 flag / user bits field 6
	LTC += '0' + '0000'
	HLP += '_' + '____'

	#hrs units / user bits field 7 / hrs tens
	LTC += ble(hrs_units,4) + '0000' + ble(hrs_tens,2)
	HLP += '---{u}____--{t}'.format(u=hrs_units, t=hrs_tens)

	# bit 58 clock flag / bit 59 flag / user bits field 8
	LTC += '0' + '0' + '0000'
	HLP += '_' + '_' + '____'

	# sync word
	LTC += '0011111111111101'
	HLP += '################'
	if as_string:
		return LTC
	else:
		return bitstring_to_bytes(LTC, bytecount=10)

def ltc(timecode):
	print(ltc_encode(timecode));

def mtc_encode(timecode, as_string=False):
	# MIDI bytes are little-endian
	# Byte 0
	#   0rrhhhhh: Rate (0–3) and hour (0–23).
	#   rr = 000: 24 frames/s
	#   rr = 001: 25 frames/s
	#   rr = 010: 29.97 frames/s (SMPTE drop-frame timecode)
	#   rr = 011: 30 frames/s
	# Byte 1
	#   00mmmmmm: Minute (0–59)
	# Byte 2
	#   00ssssss: Second (0–59)
	# Byte 3
	#   000fffff: Frame (0–29, or less at lower frame rates)
	hrs, mins, secs, frs = timecode.frames_to_tc(timecode.frames)
	framerate = timecode.framerate
	rateflags = {
		'24':    0,
		'25':    1,
		'29.97': 2,
		'30':    3
	}
	rateflag = rateflags[framerate] * 32  # multiply by 32, because the rate flag starts at bit 6

	# print('{:8} {:8} {:8} {:8}'.format(hrs, mins, secs, frs))
	if as_string:
		b0 = bbe(rateflag + hrs, 8)
		b1 = bbe(mins)
		b2 = bbe(secs)
		b3 = bbe(frs)
		# print('{:8} {:8} {:8} {:8}'.format(b0, b1, b2, b3))
		return b0+b1+b2+b3
	else:
		b = bytearray([rateflag + hrs, mins, secs, frs])
		# debug_string = '    0x{:02}     0x{:02}     0x{:02}     0x{:02}'
		# debug_array  = [ord(b[0]), ord(b[1]), ord(b[2]), ord(b[3])]
		# print(debug_string.format(debug_array))
		return b
	
def mtc_full_frame(timecode):
	# if sending this to a MIDI device, remember that MIDI is generally little endian
	# but the full frame timecode bytes are big endian
	mtc_bytes = mtc_encode(timecode)
	# mtc full frame has a special header and ignores the rate flag
	return bytearray([0xf0, 0x7f, 0x7f, 0x01, 0x01]) + mtc_bytes + bytearray([0xf7])

def mtc_quarter_frame(timecode, piece=0):
	# there are 8 different mtc_quarter frame pieces
	# see https://en.wikipedia.org/wiki/MIDI_timecode
	# and https://web.archive.org/web/20120212181214/http://home.roadrunner.com/~jgglatt/tech/mtc.htm
	# these are little-endian bytes
	# piece 0 : 0xF1 0000 ffff frame
	mtc_bytes = mtc_encode(timecode)
	this_byte = mtc_bytes[3 - piece//2]   #the order of pieces is the reverse of the mtc_encode
	if piece % 2 == 0:
		# even pieces get the low nibble
		nibble = this_byte & 15
	else:
		# odd pieces get the high nibble
		nibble = this_byte >> 4
	return bytearray([0xf1, piece * 16 + nibble])

	
def run(fps, realtime=True, duration=None, renderer=print):
	tc1 = Timecode(fps, '00:00:00:00')
	frame_size = 1/fps
	app_start = time.time()
	while 1:
		if not realtime:
			tc1.next()
			renderer(tc1)
		else:
			now_time = time.time() - app_start
		
			if now_time > tc1.frame_number * frame_size:
				renderer(tc1)
				tc1.next()
			time.sleep(0.001)
			
		if tc1.frame_number * frame_size > duration:
			break


def write_wave_file(f, data):
	header = gen_wave_header(data)
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
	
def make_ltc_wave(fps=24, duration=60, sample_rate=44100, sample_bits=8):
	max_val = 2**sample_bits - 1  # 2^8 - 1 = 0b11111111

	# each frame has 80 bytes, and each byte is represented by two "notes"
	# to represent a 0, we use FF FF or 00 00
	# to represent a 1, we use FF 00 or 00 FF
	# every double-note must start with the opposite of the previous half note

	# generate the timecode data for the entire duration
	tc = Timecode(fps, '00:01:00:00')
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

	total_samples = int(sample_rate * duration)
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
	write_wave_file(f, data)
	f.close()


tc = Timecode(24, '00:01:00:00')
for i in range(24*100):
	tc.next()
	b = mtc_full_frame(tc)
	tmp = []
	for j in range(10):
		tmp.append(hex(b[j]))
	print ('full frame: ' + ' '.join(tmp))

	for j in range(8):
		qf = mtc_quarter_frame(tc, j)
		print('{} {}'.format(hex((qf[0])),hex((qf[1]))))
		
