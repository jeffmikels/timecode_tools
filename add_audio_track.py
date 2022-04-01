#!/usr/bin/env python3

import click
import os
import subprocess

def get_tracks(fn):
	cmd = 'ffprobe -select_streams a -show_entries stream=channels -of compact=p=0:nk=1 -v 0'.split(' ')
	cmd.append(fn)
	p = subprocess.Popen(cmd,stdout=subprocess.PIPE)
	res = p.communicate()
	return int(res[0].decode().strip())

@click.command()
@click.option('--infile', '-i', type=str, required=True, help='input file')
@click.option('--outfile','-o', type=str, required=True, help='output file')
@click.option('--newaudio','-a', type=str, required=True, multiple=True, help='(can handle multiples) new audio file (must be mono)')
@click.option('--track','-t', type=int, multiple=True, help='add the new audio as which audio track(s) (defaults to next available)')
def add_track(infile, outfile, newaudio, track):
	
	# we are using multi channel audio... NOT surround sound
	# as a result, we want to specify non surround sound speaker
	# layouts. Acceptable layouts are mono, stereo, quad, hexagonal, octagonal
	# quad layout is FL+FR+BL+BR
	# hexagonal layout is FL+FR+FC+BL+BR+BC
	# octagonal layout is FL+FR+FC+BL+BR+BC+SL+SR
	print('\n\nAUDIO FILE EMBEDDING')
	print(f'Embedding Audio Files')
	print(f'Into         "{os.path.basename(infile)}"')
	
	input_items = [f'-i "{infile}"']
	input_tracks = get_tracks(infile)
	channel_map = []
	for i in range(input_tracks):
		channel_map.append(f'c{i}=c{i}')
		
	for i in range(len(newaudio)):
		item = newaudio[i]
		if i < len(track):
			target_track = track[i]
		else:
			target_track = input_tracks + 1
		print(f'Placing      "{os.path.basename(item)}"')
		print(f'At Track     #{target_track}')
		input_items.append(f'-i "{item}"')
		item_tracks = get_tracks(item)
		if (item_tracks > 1):
			print('ERROR: new audio files must be mono')
			exit()
		input_tracks = input_tracks + item_tracks;
		
		if target_track - 1 < len(channel_map):
			channel_map[target_track - 1] = f'c{target_track - 1}=c{input_tracks - 1}'
		else:
			for i in range(len(channel_map), target_track-1) :
				channel_map.append(f'c{i}=0*c0')
			channel_map.append(f'c{target_track - 1}=c{input_tracks - 1}')
	
	output_tracks = len(channel_map)
	if output_tracks != 1 and output_tracks % 2 == 1:
		output_tracks += 1

	if output_tracks > 8:
		print('ERROR: Cannot have more than 8 output tracks.')
		exit()
	
	print(f'Total Tracks #{output_tracks}')
	
	for i in range(output_tracks):
		if i > len(channel_map) - 1:
			channel_map.append(f'c{i}=0*c0')
	
	# tracks are an absolute count
	# but track names are zero indexed
	if output_tracks == 1:
		channel_layout = 'mono'
	else:
		channel_layout = ['stereo','4.0','6.0','octagonal'][output_tracks // 2 - 1]
	
	panstring = channel_layout + '|' + '|'.join(channel_map)
	cmd = f'ffmpeg -v error -stats {" ".join(input_items)} -filter_complex "amerge=inputs={len(input_items)},pan={panstring}" -c:v copy -c:a libfdk_aac -b:a 256k "{outfile}"'
	print(cmd)
	os.system(cmd)
	
add_track()
