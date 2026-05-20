import re
from urllib.parse import quote, unquote

from odt2html.exceptions import OdfNotImplementedYet

def element_empty(el):
	"""Is this element devoid of text and children?"""
	return el.text is None and el.tail is None and len(list(el)) == 0

def element_extract_text(el):
	"""
	Extract text from an ODT element and its children.
	Throw away any formatting.
	"""
	text = ""
	if el.text is not None:
		text += el.text
	else:
		text += " "
	for child_el in el:
		text += element_extract_text(child_el)
	if el.tail is not None:
		text += el.tail
	return text

def href_to_html(href):
	"""Convert an ODF href to the proper format for the web version"""
	href = re.sub(r"\.odt$", ".html", href, flags=re.IGNORECASE)		# change extension
	href = re.sub(r"/index\.html$", "/", href, flags=re.IGNORECASE)		# drop explicit index.html
	# see https://tools.ietf.org/html/rfc3986#section-3.3
	href = quote(unquote(href), safe="/~!$&'()*+,;=:@")
	return href

# Parse a dimension returning a number (possibly with decimal point) and unit
dimension_regexp = re.compile(r"(^[-0-9\.]+)((in)|(pt)|(mm)|(cm)|(px))$")

def normalize_dimensions(prop_name, prop_value):
	"""
	Parse the right-hand side of a CSS style setting, find the numeric
	dimensions and enforce a minimum size. In the process, all units
	get converted to points.
	"""
	words = []
	for word in prop_value.split(" "):
		if dimension_regexp.match(word):
			points = dimension2points(word)
			if points >= 0.8 or not prop_name.startswith("border"):
				word = "%.2fpt" % points
			elif points < 0.0001:
				word = "0pt"
			else:
				word = "thin"
		words.append(word)
	return " ".join(words)

def dimension2points(dimension):
	"""
	Convert a CSS-style dimension with units into points.
	We use this when making comparisons.
	"""
	m = dimension_regexp.match(dimension)
	if m:
		if m.group(2) == "pt":
			return float(m.group(1))
		elif m.group(2) == "in":
			return float(m.group(1)) * 72.0
		elif m.group(2) == "mm":
			return float(m.group(1)) * 72.0 / 25.4
		elif m.group(2) == "cm":
			return float(m.group(1)) * 72.0 / 2.54
		elif m.group(2) == "px":
			return float(m.group(1)) * 0.72			# about 100 DPI
	raise OdfNotImplementedYet("dimension not understood: %s" % dimension)
