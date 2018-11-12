#!/usr/bin/env python3

import time


start = time.time()
t = ''
for i in range(1000000):
    t += '1'
print (time.time() - start)
# string concatenation is slow

start = time.time()
t = []
for i in range(1000000):
    t.append('1')
''.join(t)
print (time.time() - start)
# list comprehension with final join is faster

start = time.time()
t = []
for i in range(1000000):
    t.append('1')
print (time.time() - start)
# list comprehension without final join isn't much faster

start = time.time()
t = bytearray(1000000)
for i in range(1000000):
    t[i] = 49
print (time.time() - start)
# manipulating pre-allocated byte arrays is fastest
