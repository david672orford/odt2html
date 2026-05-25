"""LXML parser for reading ODF files"""

import re

import lxml.etree as ET

# Translate namespace prefixes to URIs
namespaces = {
	"xml":       "http://www.w3.org/XML/1998/namespace",
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
	"table":     "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
	"number":    "urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0",
	"svg":       "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0",
	"form":      "urn:oasis:names:tc:opendocument:xmlns:form:1.0",
	"loext":     "urn:org:documentfoundation:names:experimental:office:xmlns:loext:1.0" ,
	}

# Translate namespace URIs to prefixes
rev_namespaces = {uri: prefix for prefix, uri in namespaces.items()}

class OdfAttribs(dict):
	"""Catch attempts to access members without a namespace prefix"""
	def get(self, key, default=None):
		assert ":" in key, key
		return super().get(key, default)
	def __getitem__(self, key):
		assert ":" in key, key
		return super().__getitem__(key)
	def __contains__(self, key):
		assert ":" in key, key
		return super().__contains__(key)

class OdfElement(ET.ElementBase):
	"""Wrap element to replace Clark notation with namespace prefixes"""
	def _init(self):

		# Strip the namespace from the tag or replace it with a prefix
		tag = ET.ElementBase.tag.__get__(self)
		assert tag[0] == "{"
		namespace, localtag = tag[1:].split("}")
		ns_prefix = rev_namespaces[namespace]
		self._tag = f"{ns_prefix}:{localtag}"

		# Strip the namespaces from the attributes, or replace them with prefixes
		attrib = OdfAttribs()
		for name, value in super().attrib.items():
			assert name[0] == "{"
			namespace, localname = name[1:].split("}")
			ns_prefix = rev_namespaces[namespace]
			attrib[f"{ns_prefix}:{localname}"] = value
		self._attrib = attrib

	@property
	def tag(self):
		return self._tag

	@property
	def attrib(self):
		return self._attrib

	def xpath(self, path):
		assert not re.search(r"/[^:]+/", path)
		assert not re.search(r"@[^:]+=", path)
		return super().xpath(path, namespaces=namespaces)

def make_odf_parser():
	parser = ET.XMLParser()
	lookup = ET.ElementDefaultClassLookup(element=OdfElement)
	parser.set_element_class_lookup(lookup)
	return parser
