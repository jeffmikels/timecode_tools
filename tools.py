#!/usr/bin/env python3
from timecode import Timecode


def bitstring_to_bytes(s, bytecount=1, byteorder='big'):
  return int(s, 2).to_bytes(bytecount, byteorder)

# binary big-endian


def bbe(n, bits=8):
  # terminal condition
  retval = ''
  if n == 0:
    retval = '0'
  else:
    retval = bbe(n//2, None) + str(n % 2)
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
    retval = str(n % 2) + ble(n//2, None)
  if bits is None:
    return retval
  else:
    return (retval + ('0'*bits))[0:bits]


def cint(n, bytecount=2):
  return int(n).to_bytes(bytecount, byteorder='little')


def units_tens(n):
  return n % 10, int(n/10)

##
# LTC functions
##
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

  # frames units / user bits field 1 / frames tens
  LTC += ble(frame_units, 4) + '0000' + ble(frame_tens, 2)
  HLP += '---{u}____-{t}'.format(u=frame_units, t=frame_tens)

  # drop frame / color frame / user bits field 2
  LTC += '00'+'0000'
  HLP += '__'+'____'

  # secs units / user bits field 3 / secs tens
  LTC += ble(secs_units, 4) + '0000' + ble(secs_tens, 3)
  HLP += '---{u}____--{t}'.format(u=secs_units, t=secs_tens)

  # bit 27 flag / user bits field 4
  LTC += '0' + '0000'
  HLP += '_' + '____'

  # mins units / user bits field 5 / mins tens
  LTC += ble(mins_units, 4) + '0000' + ble(mins_tens, 3)
  HLP += '---{u}____--{t}'.format(u=mins_units, t=mins_tens)

  # bit 43 flag / user bits field 6
  LTC += '0' + '0000'
  HLP += '_' + '____'

  # hrs units / user bits field 7 / hrs tens
  LTC += ble(hrs_units, 4) + '0000' + ble(hrs_tens, 2)
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


##
# MTC functions
##
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

# convert a bytearray back to timecode


def mtc_decode(mtc_bytes):
  rhh, mins, secs, frs = mtc_bytes
  rateflag = rhh >> 5
  hrs = rhh & 31
  fps = ['24', '25', '29.97', '30'][rateflag]
  total_frames = int(frs + float(fps) * (secs + mins * 60 + hrs * 60 * 60))
  # total frames must always be an integer above zero
  if total_frames < 1:
    total_frames = 1
  return Timecode(fps, frames=total_frames)


def mtc_full_frame(timecode):
  # if sending this to a MIDI device, remember that MIDI is generally little endian
  # but the full frame timecode bytes are big endian
  mtc_bytes = mtc_encode(timecode)
  # mtc full frame has a special header and ignores the rate flag
  return bytearray([0xf0, 0x7f, 0x7f, 0x01, 0x01]) + mtc_bytes + bytearray([0xf7])


def mtc_decode_full_frame(full_frame_bytes):
  mtc_bytes = full_frame_bytes[5:-1]
  return mtc_decode(mtc_bytes)


def mtc_quarter_frame(timecode, piece=0):
  # there are 8 different mtc_quarter frame pieces
  # see https://en.wikipedia.org/wiki/MIDI_timecode
  # and https://web.archive.org/web/20120212181214/http://home.roadrunner.com/~jgglatt/tech/mtc.htm
  # these are little-endian bytes
  # piece 0 : 0xF1 0000 ffff frame
  mtc_bytes = mtc_encode(timecode)
  this_byte = mtc_bytes[3 - piece//2]  # the order of pieces is the reverse of the mtc_encode
  if piece % 2 == 0:
    # even pieces get the low nibble
    nibble = this_byte & 15
  else:
    # odd pieces get the high nibble
    nibble = this_byte >> 4
  return bytearray([0xf1, piece * 16 + nibble])


def mtc_decode_quarter_frames(frame_pieces):
  mtc_bytes = bytearray(4)
  if len(frame_pieces) < 8:
    return None
  for piece in range(8):
    mtc_index = 3 - piece//2    # quarter frame pieces are in reverse order of mtc_encode
    this_frame = frame_pieces[piece]
    if this_frame is bytearray or this_frame is list:
      this_frame = this_frame[1]
    data = this_frame & 15      # ignore the frame_piece marker bits
    if piece % 2 == 0:
      # 'even' pieces came from the low nibble
      # and the first piece is 0, so it's even
      mtc_bytes[mtc_index] += data
    else:
      # 'odd' pieces came from the high nibble
      mtc_bytes[mtc_index] += data * 16
  return mtc_decode(mtc_bytes)
