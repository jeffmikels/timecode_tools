#!/usr/bin/env python3

from tools import cint, ltc_encode
from timecode import Timecode
import click


class MyByteArray:
  def __init__(self, size):
    self.buffer = bytearray(size)
    self.cursor = 0

  def add(self, byte):
    self.buffer[self.cursor] = byte
    self.cursor += 1


def write_wave_file(file_name, data, rate=48000, bits=8):
  header = gen_wave_header(data, rate=rate, bits=bits)
  with open(file_name, 'wb') as f:
    f.write(header)
    f.write(data)


def gen_wave_header(data, rate=48000, bits=8, channels=1):
  # integers are stored in C format
  # where 0x0000 + 1 = 0x0100 AND 0xFF00 + 1 = 0x0001
  # the following header has a specified length
  header_length = 4+4+4+4+4+2+2+4+4+2+2+4+4
  data_length = len(data)
  file_length = header_length + data_length
  header = b''
  header += b'RIFF'                              # ascii RIFF
  header += cint(file_length, 4)                  # file size data
  header += b'WAVE'                              # ascii WAVE
  header += b'fmt '                              # includes trailing space
  header += cint(16, 4)                           # length of format data (16)
  header += cint(1, 2)                            # type of format (1 is PCM)
  header += cint(channels, 2)                     # number of channels
  header += cint(rate, 4)                         # 44100 sample rate
  header += cint(rate * bits * channels / 8, 4)  # (sample rate * bits per sample * channels) / 8
  header += cint(bits * channels / 8, 2)         # (bits per sample * channels) / 8
  header += cint(bits, 2)                         # bits per sample
  header += b'data'                              # marks the beginning of the data section
  header += cint(data_length, 4)                  # size of the data section
  return header


@click.command()
@click.option('--fps', '-f',   default='24', help='frames per second, defaults to 24')
@click.option('--start', '-s', default='00:01:00:00',  help='start timecode, defaults to 00:01:00:00')
@click.option('--duration', '-d',   default=300.0, help='duration in seconds for the ltc, defaults to 300 (5 minutes)')
@click.option('--rate', '-r',   default=48000, help='sample rate, defaults to 48000')
@click.option('--bits', '-b',   default=16, help='bits per sample, defaults to 16')
def make_ltc_wave(fps, start, duration, rate, bits):
  fps = float(fps)
  duration = float(duration)
  fmt = 'pcm_u8'

  # if bits is 8, samples are unsigned values from 0 - 255
  # if bits is 16, samples should be signed from -32768 to 32767
  on_val = 255
  off_val = 0
  if bits == 16:
    fmt = 'pcm_s16le'
    on_val = 32767
    off_val = -32768
  elif bits == 32 or bits == 64:
    if bits == 32:
      fmt = 'pcm_f32le'
    else:
      fmt = 'pcm_f64le'
    on_val = 1.0
    off_val = 0.0

  total_samples = int(rate * duration)
  bytes_per_sample = bits // 8
  total_bytes = total_samples * bytes_per_sample

  # MIDI timecodes arrive in frames
  # each frame has 80 bytes, and each byte is represented by two "notes"
  # to represent a 0, we use FF FF or 00 00
  # to represent a 1, we use FF 00 or 00 FF
  # every double-note must start with the opposite of the previous half note

  # generate the MIDI timecode data for the entire duration
  tc = Timecode(fps, start)
  tc_encoded = []
  print('PREPARING MIDI TIMECODE BYTES:')
  print(f'| {start}\n| {fps} fps\n| {duration} secs')
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

  # by setting a buffer with a fixed size
  # and indexing into it, we get a tiny performance boost
  data = MyByteArray(total_bytes)
  for sample_num in range(total_samples):
    ratio = sample_num/total_samples
    pct = int(ratio * 100)
    if sample_num % 1000 == 0:
      print(f'   COMPUTING:  {total_samples}:{sample_num}  --  {pct}%', end='\r')

    double_pulse_position = len(double_pulse_data) * ratio
    dpp_intpart = int(double_pulse_position)
    this_val = int(double_pulse_data[dpp_intpart])

    if this_val == 1:
      sample = on_val
    else:
      sample = off_val

    # RIFF wav files use little endian
    sample_bytes = sample.to_bytes(bytes_per_sample, 'little', signed=bits > 8)
    for byte in sample_bytes:
      data.add(byte)

  # everything has been computed
  # prepare to write the wave file
  print()

  wave_file_name = 'ltc--{}--{}fps--{}--{}--{}secs.wav'.format(
      start.replace(':', '_'), fps, rate, fmt, duration)
  print(f'Writing WAV File: {wave_file_name}')
  write_wave_file(wave_file_name, data.buffer, rate=rate, bits=bits)
  print('DONE\n\n')


make_ltc_wave()
