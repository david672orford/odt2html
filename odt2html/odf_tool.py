import os
import zipfile
import re
from collections import OrderedDict

import lxml.etree
from lxml.etree import QName

namespaces = {
	"office":    "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
	"meta":      "urn:oasis:names:tc:opendocument:xmlns:meta:1.0",
	"style":     "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
	"xref":      "http://www.w3.org/1999/xlink",
	"text":      "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
	"fo":        "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
	"officeooo": "http://openoffice.org/2009/office",
	"xlink":     "http://www.w3.org/1999/xlink",
	"dc":        "http://purl.org/dc/elements/1.1/",
	"draw":      "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
	"table":     "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
	}

#=============================================================================
# Open and modify an ODT file
#=============================================================================

class OdfTool(object):
	def __init__(self, odt_filename:str):
		self.open(odt_filename)
		self.subfiles = {}

		self._strip = []	# Filename prefixes to skip when writing back to disk

	def open(self, odt_filename):
		self.odt_filename = odt_filename
		self.odt:zipfile.ZipFile = zipfile.ZipFile(self.odt_filename, "r")

	def get_subfile(self, subfilename):
		"""Open one of the XML files and parse it using LXML."""
		if subfilename not in self.subfiles:
			fh = self.odt.open(subfilename)
			self.subfiles[subfilename] = lxml.etree.parse(fh)
		return self.subfiles[subfilename]

	def get_pretty_text(self, subfilename):
		"""Open one of the XML files, format it for easy editing, and return the text."""
		subfile_xml = self.get_subfile(subfilename)
		return lxml.etree.tostring(subfile_xml, pretty_print=True, encoding="unicode")

	def set_pretty_text(self, subfilename, tempfilename):
		"""Replace one of the XML files with the supplied text. Undo pretty formatting."""
		new_xml = self.subfiles[subfilename] = lxml.etree.parse(tempfilename)
		whitespace = re.compile(r"^\n *$")
		for el in new_xml.iter():
			if el.text is not None and whitespace.match(el.text):
				el.text = None
			if el.tail is not None and whitespace.match(el.tail):
				el.tail = None

	# styles.xml <office:styles>: selectable by user from style list
	# content.xml <office:automatic-styles>: manual formatting performed by user
	# styles.xml <office:master-styles>: page styles
	# styles.xml <office:automatic-styles>: manual formatting of master styles
	def get_styles(self):
		return self.get_subfile("styles.xml").xpath("/office:document-styles/office:styles", namespaces=namespaces)[0]
	def get_automatic_styles(self):
		return self.get_subfile("content.xml").xpath("/office:document-content/office:automatic-styles", namespaces=namespaces)[0]
	def get_master_styles(self):
		return self.get_subfile("styles.xml").xpath("/office:document-styles/office:master-styles", namespaces=namespaces)[0]
	def get_master_automatic_styles(self):
		return self.get_subfile("styles.xml").xpath("/office:document-styles/office:automatic-styles", namespaces=namespaces)[0]

	def get_metadata(self):
		"""Return the document metadata"""
		return self.get_subfile("meta.xml").xpath("/office:document-meta/office:meta", namespaces=namespaces)[0]

	def get_text(self):
		"""Return the document text element"""
		return self.get_subfile("content.xml").xpath("/office:document-content/office:body/office:text", namespaces=namespaces)[0]

	def set_default_language(self, language, country):
		"""Set the default language for styles"""
		changes = 0
		for el in self.get_styles().xpath("./style:default-style/style:text-properties", namespaces=namespaces):
			if el.attrib.get("{%s}language" % namespaces["fo"]) != language:
				el.attrib["{%s}language" % namespaces["fo"]] = language
				changes += 1
			if el.attrib.get("{%s}country" % namespaces["fo"]) != country:
				el.attrib["{%s}country" % namespaces["fo"]] = country
				changes += 1
		return changes

	def strip_rsid(self):
		"""
		It seems that document revisions are marked using dummy styles. Remove the
		attributes related to revisions so that the dummy styles will be stripped
		when the document is next edited.
		"""
		changes = 0
		for styles in (self.get_styles(), self.get_automatic_styles()):
			for el in styles.iterdescendants():
				for attrib in ("{%s}rsid" % namespaces["officeooo"], "{%s}paragraph-rsid" % namespaces["officeooo"]):
					if attrib in el.attrib:
						del el.attrib[attrib]
						changes += 1
		print("  ** strip rsid: %d" % changes)
		return changes

	def strip_en(self):
		"""Strip explicit English language from styles"""
		changes = 0
		for styles in (self.get_styles(), self.get_automatic_styles()):
			for el in styles.xpath("./style:style/style:text-properties", namespaces=namespaces):
				language = el.attrib.get("{%s}language" % namespaces["fo"])
				if language == "en":
					del el.attrib["{%s}language" % namespaces["fo"]]
					del el.attrib["{%s}country" % namespaces["fo"]]
					changes += 2
		print("  ** strip en: %d" % changes)
		return changes

	# Remove attributes related to Asian fonts from the styles.
	def strip_asian_fonts(self):
		changes = 0
		for styles in (self.get_styles(), self.get_automatic_styles()):
			for el in styles.iterdescendants():
				for attrib in (
						"{%s}font-family-asian" % namespaces["style"],
						"{%s}font-family-generic-asian" % namespaces["style"],
						"{%s}font-name-asian" % namespaces["style"],
						"{%s}font-weight-asian" % namespaces["style"],
						"{%s}font-style-asian" % namespaces["style"],
						"{%s}font-size-asian" % namespaces["style"],
						"{%s}font-pitch-asian" % namespaces["style"],
						"{%s}language-asian" % namespaces["style"],
						"{%s}country-asian" % namespaces["style"],
						"{%s}font-family-complex" % namespaces["style"],
						"{%s}font-family-generic-complex" % namespaces["style"],
						"{%s}font-name-complex" % namespaces["style"],
						"{%s}font-weight-complex" % namespaces["style"],
						"{%s}font-style-complex" % namespaces["style"],
						"{%s}font-size-complex" % namespaces["style"],
						"{%s}font-pitch-complex" % namespaces["style"],
						"{%s}language-complex" % namespaces["style"],
						"{%s}country-complex" % namespaces["style"]
					):
					if attrib in el.attrib:
						del el.attrib[attrib]
						changes += 1
		print("  ** strip asian: %d" % changes)
		return changes

	def strip_thumbnails(self):
		"""Remove document thumbnails"""
		changes = 0
		for item in self.odt.infolist():
			if item.filename.startswith("Thumbnails/"):
				changes += 1
		self._strip.append("Thumbnails/")
		print("  ** strip thumbs: %d" % changes)
		return changes

	def strip_configurations(self):
		"""Remove Write configuration"""
		changes = 0
		for item in self.odt.infolist():
			if item.filename.startswith("Configurations2/"):
				changes += 1
		self._strip.append("Configurations2/")
		print("  ** strip conf: %d" % changes)
		return changes

	# Search for given text and replace it.
	def replace(self, search, replace):
		body_text = self.get_text()
		changes = 0
		for xpath in (".//text:h", ".//text:p", ".//text:span", ".//text:a"):
			for el in body_text.xpath(xpath, namespaces=namespaces):
				if el.text and search in el.text:
					el.text = el.text.replace(search, replace)
					changes += 1
				if el.tail and search in el.tail:
					el.tail = el.tail.replace(search, replace)
					changes += 1
		return changes

	# Get a user-defined item from the document's metadata
	def get_user_metadata(self, name):
		meta = self.get_metadata()
		for el in meta.xpath("./meta:user-defined", namespaces=namespaces):
			if el.attrib["{%s}name" % namespaces["meta"]] == name:
				return el.text
		return None

	# Set a user-defined item in the document's metadata
	def set_user_metadata(self, name, value):
		changes = 0
		found = False
		meta = self.get_metadata()
		for el in meta.xpath("./meta:user-defined", namespaces=namespaces):
			if el.attrib["{%s}name" % namespaces["meta"]] == name:
				if el.text != value:
					el.text = value
					changes += 1
				found = True
		if not found:
			el = lxml.etree.Element("{%s}user-defined" % namespaces["meta"])
			el.attrib["{%s}name" % namespaces["meta"]] = name
			if "date" in name:
				el.attrib["{%s}value-type" % namespaces["meta"]] = "date"
			el.text = value
			meta.append(el)
			changes += 1
		for el in self.get_master_styles().xpath(".//text:user-defined", namespaces=namespaces):
			if el.attrib.get("{%s}name" % namespaces["text"]) == name and el.text != value:
				el.text = value
				changes += 1
		return changes

	# Rewrite the ODT file
	def save(self):
		assert self.odt
		tmp_odt_filename = "%s.tmp" % self.odt_filename
		bak_odt_filename = "%s~" % self.odt_filename

		# Copy the document zipfile to a new zipfile replacing the edited subfile when we see it go by.
		with zipfile.ZipFile(tmp_odt_filename, "w", compression=zipfile.ZIP_DEFLATED) as new_odt:
			for item in self.odt.infolist():
				for strip in self._strip:
					if item.filename.startswith(strip):
						break
				else:			# not skipt
					if item.filename in self.subfiles:		# if we opened this subfile,
						with new_odt.open(item.filename, "w") as fh:
							self.subfiles[item.filename].write(
								fh,
								pretty_print=False,
								encoding="utf-8",
								xml_declaration=True
								)
					else:
						new_odt.writestr(item, self.odt.read(item.filename))

		self.odt.close()
		#self.odt = None
		self.subfiles = {}

		if os.path.exists(bak_odt_filename):
			os.unlink(bak_odt_filename)
		os.rename(self.odt_filename, bak_odt_filename)
		os.rename(tmp_odt_filename, self.odt_filename)

#=============================================================================
# Styles
#=============================================================================

class Styles(OrderedDict):
	def __init__(self, odt):
		OrderedDict.__init__(self)
		self.add_styles("styles.xml", odt.get_styles())
		self.add_styles("styles.xml-master", odt.get_master_styles())
		self.add_styles("styles.xml-automatic", odt.get_master_automatic_styles())
		self.add_styles("content.xml", odt.get_automatic_styles())
		for container in (odt.get_text(), odt.get_styles(), odt.get_master_styles(), odt.get_master_automatic_styles(), odt.get_automatic_styles()):
			for el in container.iterdescendants():
				for key in (
						"{%s}style-name" % namespaces["text"],
						"{%s}style-name" % namespaces["draw"],
						"{%s}style-name" % namespaces["table"],
						"{%s}page-layout-name" % namespaces["style"],
						"{%s}master-page-name" % namespaces["style"]
					):
					style_name = el.attrib.get(key)
					if style_name:
						self[style_name].set_used()
	def add_styles(self, group_name, container_el):
		for style_el in container_el:
			self.add_style_obj(Style(self, group_name, style_el))
	def add_style_obj(self, style):
		self[style.name] = style

class Style(object):
	def __init__(self, styles, group_name, style_el):
		self.styles = styles
		self.group_name = group_name
		self.el = style_el
		self.tag = QName(style_el).localname
		self.name = style_el.attrib.get("{%s}name" % namespaces["style"])
		self.parent_style_name = style_el.attrib.get("{%s}parent-style-name" % namespaces["style"])
		self.used = False
		self.used_directly = False
		self.styles[self.name] = self
	def __str__(self):
		return "<Style %s %s %s used=%s>" % (self.group_name, self.tag, self.name, str(self.used))
	def set_used(self, directly=True):
		self.used = True
		if directly:
			self.used_directly = True
		if self.parent_style_name is not None:
			self.styles[self.parent_style_name].set_used(False)
	def delete(self):
		self.el.getparent().remove(self.el)
