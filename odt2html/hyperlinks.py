import os
import re
import json
from urllib.parse import urlparse, quote, unquote
from urllib.request import url2pathname

import lxml.etree as ET
from lxml.builder import E

from odt2html.exceptions import OdfNotImplementedYet, OdfBadPlayer
from odt2html.utils import href_to_html, element_extract_text

class HyperlinkConverter:
	def __init__(self, converter):
		# Things this code still needs from the converter object now that
		# it has been partially encapsulated
		self.odt_filename = converter.odt_filename
		self.output_dirname = converter.output_dirname
		self.opts = converter.opts
		self.html_body = converter.html_body
		self.add_script = converter.add_script
		self.add_script_file = converter.add_script_file
		self.subdocs_by_href = converter.subdocs_by_href

		self.playlist = []
		self.require_zoom_image = False

	def convert(self, odt_el:ET._Element) -> ET._Element:
		"""Called from convert_element() when it encounters an <a> tag"""

		assert odt_el.tag in ("text:a", "draw:a"), odt_el.tag

		if self.opts.debug:
			print("Hyperlink:", odt_el.attrib)

		href = odt_el.attrib["xlink:href"]
		target = odt_el.attrib.get("office:target-frame-name")

		if target == "player":
			html_a_el = self.convert_player(odt_el, href)
		else:
			html_a_el = self.convert_base(odt_el, href, target)

		assert html_a_el.tag == "a"
		html_a_el.tail = ""
		return html_a_el

	def convert_base(self, odt_el:ET._Element, href:str, target:str|None) -> ET._Element:
		# Apply fixups to the href
		if href.split(":")[0] in ("http", "https", "ftp", "mailto"):	# Internet link
			if self.opts.debug:
				print("  External link")
		elif href.startswith("../"):				# Intrasite link relative to zip root (but outside)
			if self.opts.debug:
				print("  Intrasite link")
			href_html = href_to_html(href)			# convert extension
			if href_html in self.subdocs_by_href:	# in same master document?
				if self.opts.split_by_sections:
					href = "content%s.html" % self.subdocs_by_href[href_html]
				else:
					href = "#%s" % self.subdocs_by_href[href_html]
			else:
				# Make sure target file (likely an ODT or HTML file) exists
				fs_path = os.path.join(os.path.dirname(self.odt_filename), url2pathname(href[3:]))
				fs_path = fs_path.encode("utf-8")	# FIXME: assumes file system encoding is UTF-8
				if not os.path.exists(fs_path):
					print("  Warning: broken link: %s" % fs_path)
				# Whether it exists or not, point to the HTML version
				href = href_html[3:]
		elif href.startswith("#zoom_image"):
			if self.opts.debug:
				print("  Zoomable image")
			self.require_zoom_image = True
		elif href.startswith("#"):					# Intradocument link
			if self.opts.debug:
				print("  Intradocument link")
		else:
			raise OdfNotImplementedYet("href of unimplemented type: %s" % href)

		# Generate the HTML <a> tag and apply attributes
		html_el:ET._Element = E.a({"href":href})
		if target is not None:
			html_el.attrib["target"] = target
		if href.endswith(".svg"):					# FIXME: not sure we need this long-term
			html_el.attrib["type"] = "image/svg+xml"
		name = odt_el.attrib.get("office:name")
		if name is not None:
			html_el.attrib["title"] = name

		return html_el

	# We provide a special hyperlink target called "player" which plays an audio
	# or video file in a popup player. This target type is our own invention but
	# it is compatible with the ODF specification.
	def convert_player(self, odt_el:ET._Element, href:str) -> ET._Element:
		if self.opts.debug:
			print("Player:", href)

		# If the href begins with "../", it points to a local file outside
		# the ODF file. Such hrefs are described as a "Document" links in
		# the Libreoffice GUI. The ".." reprents a move up from inside the
		# ZIP file.
		if href.startswith("../"):

			# drop "../", remove URL quoting to get unicode
			filename = unquote(href[3:])

			# FIXME: how exactly does this work?
			path_from_cwd = os.path.join(self.output_dirname, filename)

			# If it is a JSON file, we assume it is a media manifest file such as
			# created by our odt2html-mkmanifest.
			if os.path.splitext(filename)[1].lower() == ".json":
				if self.opts.debug:
					print("  Play from a pre-generated media manifest")
				with open(path_from_cwd) as f:
					manifest = json.load(f)
				manifest["basedir"] = quote(os.path.dirname(filename))
				if not ("audio" in manifest or "video" in manifest):
					raise OdfBadPlayer("Media manifest %s is empty" % path_from_cwd)

			# Otherwise is is presumably a single media file. We will
			# create a basic manifest describing it.
			else:
				if self.opts.debug:
					print("  Play a single local file")
				mediatype, mimetype = self.filetype_from_filename(filename)
				manifest = {
					"basedir": quote(os.path.dirname(filename)),
					"title": element_extract_text(odt_el),
					mediatype: [
						{
						"mimetype": mimetype,
						"src": quote(os.path.basename(filename)),
						"filesize": os.path.getsize(path_from_cwd),
						"aspect_ratio": "4:3"
						}]
					}

		# Link to Youtube video
		elif "www.youtube.com/watch?v=" in href:
			if self.opts.debug:
				print("  Play a video on Youtube")

			# Extract Youtube video ID from the URL
			m = re.search(r"v=(.+)$", href)
			if not m:
				raise OdfBadPlayer("Failed to parse Youtube link")

			manifest = {
				"title": element_extract_text(odt_el),
				"youtube": m.group(1)
				}

		# Other "Internet" link
		elif re.search(r"^https?:", href, re.I):
			if self.opts.debug:
				print("  Media is in a remote file")

			mediatype, mimetype = self.filetype_from_url(href)
			manifest = {
				mediatype: [
					{
					"mimetype": mimetype,
					"src": href,
					}]
				}

		# Some other kind of link
		else:
			raise OdfBadPlayer("Unsupported URL: %s" % href)

		# If the name attribute of the link tag is in the format "PlayX",
		# there ought to be a corresponding ODF section named "TextX". Save
		# the "X" part so that the player can move a highlighter through
		# the text as the recording plays.
		link_name = odt_el.attrib.get("office:name")
		if link_name and link_name.startswith("Play"):
			manifest["player_id"] = link_name[4:]

		# The media manifest is finished.
		if self.opts.debug:
			for line in json.dumps(manifest, indent=2, separators=(",",":"), ensure_ascii=False).split("\n"):
				print("  %s" % line)

		self.playlist.append(manifest)

		# Create the <A> element. It identifies the recording by playlist index number.
		# As soon as we have done that we add the recording to the playlist.
		# Order is important here!
		a_el:ET._Element = E.a({
			"class":"play_link",
			"href":"javascript:play(%d)" % len(self.playlist)
			})
		if "title" in manifest:
			a_el.attrib["title"] = manifest["title"]

		return a_el

	# File types supported by our embedded player
	playable_file_extensions = {
		".mp3": ("audio", "audio/mpeg"),
		".ogg": ("audio", "audio/ogg"),
		".mp4": ("video", "video/mp4"),
		".webm": ("video", "video/webm")
		}

	def filetype_from_filename(self, filename):
		ext = os.path.splitext(filename)[1].lower()
		return self.filetype_from_ext(ext, filename)

	def filetype_from_url(self, url):
		path = urlparse(url).path
		ext = os.path.splitext(path)[1].lower()
		return self.filetype_from_ext(ext, url)

	def filetype_from_ext(self, ext, url):
		if ext == "":
			raise AssertionError("Filename has no extension: %s" % url)
		if ext not in self.playable_file_extensions:
			raise AssertionError("Extension %s not supported by player: %s" % url)
		return self.playable_file_extensions[ext]

	def run(self):
		"""
		If there are links to audio and video files to be played in our popup
		player, write the list of these files out as a JavaScript variable.
		"""
		if len(self.playlist):

			# Player IDs connect players with sections of text with a moving highlight.
			# Delete presumed player IDs which do not match such a section.
			for item in self.playlist:
				if "player_id" in item and not self.html_body.xpath(".//div[@id='Text%s']" % item["player_id"]):
					del item["player_id"]

			self.add_script(
				"\nvar playlist=" + json.dumps(self.playlist, indent=1, separators=(",",":"), ensure_ascii=False) + ";\n"
				)

			# Load the popup player
			self.add_script_file("%s/player%s.js" % (self.opts.player_lib_dir, self.opts.player_version))

		# If we have any images with zooming enabled, include the zoomer code
		if self.require_zoom_image:
			self.add_script_file("%s/zoom_image%s.js" % (self.opts.player_lib_dir, self.opts.zoom_image_version))
