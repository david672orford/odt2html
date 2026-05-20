"""Speaking Table Cells"""

import os
import re
from urllib.parse import quote

from odt2html.utils import element_extract_text

class TDSound:
	def __init__(self, converter):
		self.debug = converter.debug
		self.output_dirname = converter.output_dirname
		self.html_body = converter.html_body
		self.add_script = converter.add_script
		self.add_css = converter.add_css
		self.config = converter.metadata["TD Sound"]

	def run(self):
		"""
		Go through the generated HTML, identify speaking table cells, load the
		JavaScript and CSS resources required, and hook the cells up.
		"""
		if self.debug:
			print("Enabling TD sound...")

		td_sound_lang, td_sound_path = self.config.split(":")
		m = re.match(r"^(.+)\.txt$", td_sound_path)
		if m:
			td_sound_finder = LabelSoundFinder(self.output_dirname, m.group(1))
		else:
			td_sound_finder = DirSoundFinder(self.output_dirname, td_sound_path)

		for td in self.html_body.xpath(".//td"):
			for el in ((td,) + tuple(td)):		# Iterate through the <TD> and its immediate children
				if el.attrib.get("lang") == td_sound_lang or td_sound_lang == "*":
					text = element_extract_text(el).strip()
					if text:
						url = td_sound_finder.find(text)
						if url:
							self.require_bgplay = True
							td.attrib["onclick"] = 'bgplay("%s")' % url
							td.attrib["class"] = td.attrib.get("class","") + " bgplay"
						if self.debug:
							print("  %s TD: %s %s" % (td_sound_lang, text, "OK" if url else "Missing"))
						break

		# Insert the code for the player inline.
		self.add_script(
			"""
			if(!window.analytics) window.analytics = function() {};
			function bgplay(url) {
				if(!bgplay.has_ogg)
					url = url.replace(".ogg", ".mp3");
				bgplay.player.src = url;
				bgplay.player.play();
				analytics("TD Sound", "play", url);
			}
			bgplay.player = new Audio();
			bgplay.has_ogg = bgplay.player.canPlayType("audio/ogg; codecs=vorbis")
			""".replace("\n\t\t\t\t","\n")
			)

		# Add extra style rules to put a blue border around each and give them a hover effect.
		self.add_css("""
			TD.bgplay, DIV.wrap > DIV.bgplay {border: 1px solid blue !important; cursor: pointer}
			TD.bgplay:hover, DIV.wrap > DIV.bgplay:hover {background-color: #f0f0f0}
			""")

class LabelSoundFinder:
	"""Audacity label file with the labels in the order in which they will be used"""
	def __init__(self, output_dirname:str, soundfile_basename:str):
		self.output_dirname = output_dirname
		self.base_url = quote(soundfile_basename)
		self.labels = []
		with open(os.path.join(self.output_dirname, "%s.txt" % soundfile_basename), "r", encoding="utf-8") as f:
			for line in f:
				start, stop, text = line.rstrip().split("\t")
				assert re.match(r"^\d+\.\d+$", start)
				assert re.match(r"^\d+\.\d+$", stop)
				self.labels.append([text, "t=%s,%s" % (start, stop)])
		print("labels:", self.labels)
	def find(self, text:str):
		text = text.replace("\u0301","")	# Remove stress marks.
		text = text.replace("ё", "е")		# Audacity will not accept ё
		if len(self.labels) > 0 and self.labels[0][0] == text:
			label = self.labels.pop(0)
			return "%s.ogg#%s" % (self.base_url, label[1])
		else:
			return None

class DirSoundFinder:
	"""Directory of individual sound files"""
	def __init__(self, output_dirname:str, td_sound_dir:str):
		self.output_dirname = output_dirname
		self.td_sound_dir = td_sound_dir
		self.dup_counts = {}
	def find(self, text:str):
		text = text.replace("\u0301","")	# Remove stress marks.
		dup_count = self.dup_counts[text] = self.dup_counts.get(text,0) + 1
		for filename in (
				"%s/%s-%d" % (self.td_sound_dir, text, dup_count),
				"%s/%s" % (self.td_sound_dir, text),
				"%s/%s" % (self.td_sound_dir, text.replace("?",""))
				):
			if os.path.exists("%s/%s.ogg" % (self.output_dirname, filename)) and os.path.exists("%s/%s.mp3" % (self.output_dirname, filename)):
				#url = "%s/%s.ogg" % (self.output_dirname, filename)
				url = "%s.ogg" % filename
				return quote(url)
		return None
