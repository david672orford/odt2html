"""Load Images from the ODT file"""

import zipfile
from base64 import b64encode

import lxml.etree as ET

from odt2html.exceptions import OdfNotImplementedYet

class Odt2HtmlImages(list):
	def __init__(self, converter):
		self.odt = converter.odt
		self.opts = converter.opts
	def add(self, href):
		image = Odt2HtmlImage(self.odt, href, self.opts.svg2png)
		if self.opts.use_data_urls:
			return image.get_data_url()
		else:
			self.append(image)
			return image.filename

class Odt2HtmlImage:
	def __init__(self, odt:zipfile.ZipFile, filename:str, svg2png:bool):
		self.odt = odt
		self.filename = filename
		self.svg2png = svg2png

		if self.filename.endswith(".png"):
			self.mimetype = "image/png"
			self.compression = zipfile.ZIP_STORED
		elif self.filename.endswith(".gif"):
			self.mimetype = "image/gif"
			self.compression = zipfile.ZIP_STORED
		elif self.filename.endswith(".jpg"):
			self.mimetype = "image/jpeg"
			self.compression = zipfile.ZIP_STORED
		elif self.filename.endswith(".svg"):
			self.mimetype = "image/svg+xml"
			self.compression = zipfile.ZIP_DEFLATED
		else:
			raise OdfNotImplementedYet("Href extension not recognized: %s" % self.filename)

		self.original_filename = self.filename
		self.original_mimetype = self.mimetype

		if self.mimetype == "image/svg+xml" and self.svg2png:
			self.filename = "%s.png" % self.filename
			self.mimetype = "image/png"
			self.compression = zipfile.ZIP_STORED

	def get_data(self, pretty_print=True) -> bytes:
		"""Return image data as bytes"""
		if self.original_mimetype == "image/svg+xml":
			if self.svg2png:
				import cairo
				import rsvg
				import StringIO
				svg = rsvg.Handle()
				svg.write(self.odt.open(self.original_filename).read())
				svg.close()
				width, height = svg.get_dimension_data()[:2]
				surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
				svg.render_cairo(cairo.Context(surface))
				out_fh = StringIO.StringIO()
				surface.write_to_png(out_fh)
				return out_fh.getvalue()
			else:
				tree = ET.parse(self.odt.open(self.original_filename))
				# FIXME: not sure why we need to take a list here. Also, shouldn't there
				# be just one element, namely <svg>?
				for el in list(tree.iter()):
					self.prune_svg(el)
				return ET.tostring(tree, pretty_print=pretty_print, encoding="utf-8")	# yes, utf-8
		else:
			return self.odt.open(self.original_filename).read()

	def get_data_url(self) -> str:
		# http://www.websiteoptimization.com/speed/tweak/inline-images/
		image_data = self.get_data(pretty_print=False)
		return "data:%s;base64,%s" % (self.mimetype, b64encode(image_data).decode("ascii"))

	def prune_svg(self, element):
		"""
		Remove SVG elements and attributes inserted by Inkscape but which
		are not needed for display in a web browser.
		"""
		for key in element.attrib.keys():
			if key.startswith("{http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd}"):
				del element.attrib[key]
			elif key.startswith("{http://inkscape.sourceforge.net/DTD/sodipodi-0.dtd}"):
				del element.attrib[key]
			elif key.startswith("{http://www.inkscape.org/namespaces/inkscape}"):
				del element.attrib[key]
		for child in list(element):
			#print(child.tag)
			if child.tag.startswith("{http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd}"):
				element.remove(child)
			if child.tag.startswith("{http://inkscape.sourceforge.net/DTD/sodipodi-0.dtd}"):
				element.remove(child)
			elif child.tag.startswith("{http://www.inkscape.org/namespaces/inkscape}"):
				element.remove(child)
			elif child.tag == "{http://www.w3.org/2000/svg}metadata":
				element.remove(child)
			else:
				self.prune_svg(child)
