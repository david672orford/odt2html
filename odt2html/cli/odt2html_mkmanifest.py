"""Create a JSON manifest file listing the various"""

import argparse
import os
import re
import json
import urllib.parse
import subprocess

class MediafileInfo(object):
	"""Use Ffmpeg to examine a media file"""

	def __init__(self, video_filename):
		args = "ffprobe -v quiet -print_format json -show_format -show_streams".split(" ")
		args.append(video_filename)
		self.ffprobe = json.loads(subprocess.check_output(args).decode("utf-8"))
		self.video_stream = None
		for stream in self.ffprobe["streams"]:
			if stream["codec_type"] == "video":
				self.video_stream = stream
				break
		assert self.video_stream is not None

	def get_dimensions(self):
		return (self.video_stream["width"], self.video_stream["height"])

	def get_aspect_ratio(self):
		ratio = self.video_stream["display_aspect_ratio"]
		if ratio == "0:1":		# Observed in JW.ORG videos
			return "16:9"
		else:
			return ratio

	def get_codecs(self):
		codecs = []
		for stream in self.ffprobe["streams"]:
			if stream["codec_name"] == "png":
				continue
			if stream["codec_tag_string"] == "avc1":
				profiles = {
					"Constrained Baseline": "42E0",
					"Baseline": "42E0",
					"Main": "4D40",
					"High": "6400"
					}
				codec = "avc1.%s%02X" % (profiles[stream["profile"]], stream["level"])
			elif stream["codec_tag_string"] == "mp4a":
				if stream["codec_name"] == "aac":
					if stream["profile"] == "LC":
						codec = "mp4a.40.2"
					elif stream["profile"] == "HE-AAC":
						codec = "mp4a.40.5"
					else:
						assert False, "mp4a profile=%s" % stream["profile"]
				elif stream["codec_name"] == "mp3":
					#codec = "mp4a.40.34"		# Apple, supposedly non-standard
					codec = "mp3"
				else:
					assert False
			else:
				codec = stream["codec_name"]
			codecs.append(codec)
		return ",".join(codecs)

	def get_filesize(self):
		return int(self.ffprobe["format"]["size"])

	def get_duration(self):
		return int(float(self.ffprobe["format"]["duration"]) + 0.5)

def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	_=parser.add_argument("-o", dest="manifest", default="manifest.json")
	_=parser.add_argument("--title", dest="title")
	_=parser.add_argument("filenames", nargs="+", help="List of media files to include")
	opts = parser.parse_args()

	manifest = {}
	audio = []
	video = []

	if opts.title:
		manifest["title"] = opts.title

	print("%s (%s)" % (opts.manifest, opts.title))
	for filename in opts.filename:

		if "*" in filename:		# unresolved wildcard
			continue

		if filename.endswith(".vtt") and not os.path.exists(filename):
			continue

		print("  %s..." % filename)

		if re.match(r"^https?://", filename, re.I):
			src = filename
		else:
			src = urllib.parse.quote(filename)

		if filename.endswith(".mp3"):
			info = MediafileInfo(filename)
			audio.append({
				"mimetype":"audio/mpeg",
				"codecs":info.get_codecs(),
				"src":src,
				"filesize":info.get_filesize()
				})
		elif filename.endswith(".ogg"):
			audio.append({
				"mimetype":"audio/ogg",
				"codecs":info.get_codecs(),
				"src":src,
				"filesize":info.get_filesize()
				})
		elif filename.endswith(".mp4"):
			info = MediafileInfo(filename)
			video.append({
				"mimetype":"video/mp4",
				"codecs":info.get_codecs(),
				"src":src,
				"filesize":info.get_filesize(),
				"framesize":info.get_dimensions(),
				"aspect_ratio":info.get_aspect_ratio(),
				})
			manifest["duration"] = info.get_duration()
		elif filename.endswith(".webm"):
			info = MediafileInfo(filename)
			video.append({
				"mimetype":"video/webm",
				"codecs":info.get_codecs(),
				"src":src,
				"filesize":info.get_filesize(),
				"framesize":info.get_dimensions(),
				"aspect_ratio":info.get_aspect_ratio(),
				})
			manifest["duration"] = info.get_duration()
		elif filename.endswith(".m3u8"):
			manifest["hls"] = urllib.parse.quote(filename)
		elif filename.endswith(".mpd"):
			manifest["dash"] = urllib.parse.quote(filename)
		elif filename.endswith(".vtt"):
			manifest["vtt"] = urllib.parse.quote(filename)

	if len(audio):
		manifest["audio"] = audio
	if len(video):
		manifest["video"] = sorted(video, key=lambda item: item["filesize"])

	# Write the completed manifest to a file
	with open(options.manifest,"w") as fh:
		json.dump(manifest, f, sort_keys=True, indent=2, separators=(",", ": "), ensure_ascii=False)

	return 0
