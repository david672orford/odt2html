"""
These classes take ODF stylesheets and convert them to CSS stylesheets.
"""

import re
import fnmatch
import textwrap
from collections import UserDict

import lxml.etree as ET

from odt2html.exceptions import OdfNotImplementedYet, OdfInvalid
from odt2html.config import Odt2HtmlConfig
from odt2html.utils import normalize_dimensions, dimension2points

class FontFace:
	def __init__(self, font_face:ET._Element):
		self.name = font_face.attrib["style:name"]
		self.font_family = font_face.attrib["svg:font-family"]
		self.font_family_generic = font_face.attrib.get("style:font-family-generic")
		self.font_pitch = font_face.attrib.get("style:font-pitch")

	# Generic font family names in ODF are different from those in CSS!
	font_family_map = {
		"roman": "serif",
		"swiss": "sans-serif",
		"modern": "monospace",
		"script": "cursive",
		"decorative": "fantasy",
		"system": "system-ui",
		}

	def get_css(self, font_support_level:int) -> str:
		font_families = []

		# Specific font family name
		if font_support_level >= 2:
			font_families.append(self.font_family)

		# Generic font family name
		if self.font_family_generic is not None:
			value = self.font_family_map.get(self.font_family_generic)
			if value is not None:
				font_families.append(value)

		# Finally, even more generic
		if self.font_pitch == "fixed":
			font_families.append("monospace")

		# FIXME: OpenSymbol triggers this
		#assert len(font_families) > 0

		return ",".join(font_families)

class FontFaces(UserDict):
	pass

class BaseStyle:
	"""Represents an ODF style rule"""
	def __init__(self, family:str, name:str, parent, template:str):
		self.family:str = family
		self.name:str = name			# text:style-name from ODF file
		self.parent = parent
		self.template:str = template	# printf()-style template
		self.properties = {}			# CSS to put inside the curly brackets
		self.media = None				# media query condition
		self.used = False				# mentioned in document?
		self.tag_override = None		# change <p> or <span> to this
		self.break_before = None		# "page" for page break before
		self.language = None			# not CSS, but where else can we put this?
		self.simplified_td = False

		if self.parent is not None:
			self.properties.update(parent.properties)
			self.media = parent.media
			self.break_before = parent.break_before
			self.language = parent.language

		tag_override = {
			("text", "Emphasis"): "i",			# <em> would also be appropriate
			("text", "Strong_20_Emphasis"): "b",
			("paragraph", "Quotations"): "blockquote",
			}.get((family, name))
		if tag_override is not None:
			self.tag_override = tag_override
			self.template = tag_override.upper() + ".%s"

	def __str__(self):
		return f"<Style family={repr(self.family)} name={repr(self.name)} template={repr(self.template)}>"

	@property
	def className(self):
		"""ODF style nameconverted to legal CSS class name"""
		return self.name.replace(".","_").replace("_20_","_")

	def get_template(self):
		return self.template

	def property_match(self, pattern:str):
		"""Test whether the style has a properties matching a wildcard expression"""
		return len(fnmatch.filter(self.properties.keys(), pattern)) > 0

	def is_instance_of(self, class_name:str):
		style = self
		while style is not None:
			if style.name == class_name:
				return True
			style = style.parent
		return False

	def get_css(self, css_version:float):
		"""Return a CSS rule respresenting this style"""
		style_text = "%s{%s}" % (
			self.get_template() % self.className,
			";".join(["%s:%s" % (name, value) for name, value in self.properties.items()])
			)
		if self.media is not None and css_version >= 3.0:
			style_text = "@media %s { %s }" % (
				self.media,
				style_text
				)
		return style_text

class Style(BaseStyle):
	"""Represents an ODF style rule other than list"""
	def __init__(self, odt_style:ET._Element, parent:BaseStyle|None, fonts:FontFaces, opts:Odt2HtmlConfig):
		assert odt_style.tag == "style:style"

		family = odt_style.attrib["style:family"]
		template = {
			"text": "SPAN.%s",
			"paragraph": ".%s",			# P or H[12345], plus simplified LI and TD
			"table": "TABLE.%s",
			"table-column": "COL.%s",
			"table-row": "TR.%s",
			"table-cell": "__AUTO__",
			"graphic": ".%s",			# <IMG> or <DIV> or <NAV>
			"section": "DIV.%s",

			"drawing-page": "DIV.%s"
			}.get(family)
		if template is None:
			raise OdfNotImplementedYet(f"Style family {family} not implemented")

		super().__init__(family, odt_style.attrib["style:name"], parent, template)

		self.load_children(odt_style, fonts, opts)

	def load_children(self, odt_style:ET._Element, fonts:FontFaces, opts:Odt2HtmlConfig):
		# Process the <style:style>'s child elements.
		for el in odt_style:
			if opts.debug:
				print("    <%s %s>" % (
					el.tag,
					"\n        ".join([f"{name}={repr(value)}" for name, value in el.attrib.items()])
					))
			if not el.tag.endswith("-properties"):
				if opts.debug:
					print("      Unimplemented style child: %s" % el.tag)
				continue

			# Convert properties which are generally applicable to block items.
			for prop in (
					"margin", "margin-left", "margin-right", "margin-top", "margin-bottom",
					"padding", "padding-left", "padding-right", "padding-top", "padding-bottom",
					"border", "border-left", "border-right", "border-top", "border-bottom",
				):
				value = el.attrib.get(f"fo:{prop}")
				if value is not None:
					if value != "100%":	# don't know what 100% is supposed to mean, but it is poison...
						self.properties[prop] = normalize_dimensions(prop, value)

			if el.tag == "style:section-properties":
				for el2 in el:
					if el2.tag == "style:columns":
						for prop in ("column-count", "column-gap"):
							value = el2.attrib.get(f"fo:{prop}")
							if value is not None:
								self.media = "(min-width:8in)"
								self.properties[prop] = value
								self.properties["-webkit-%s" % prop] = value
								self.properties["-moz-%s" % prop] = value
								self.properties["clear"] = "both"		# looks better this way

			# To text blocks
			elif el.tag == "style:paragraph-properties":
				for prop in ("text-align", "text-indent", "background-color"):
					value = el.attrib.get(f"fo:{prop}")
					if value is not None:
						self.properties[prop] = value

				line_height = el.attrib.get("fo:line-height")
				if line_height is not None:
					# Convert percentage line height to multiplication factor because percentage
					# line height is inherited differently in ODF and in CSS.
					m = re.match(r"^(\d+)%$", line_height)
					if m:
						line_height = "%.2f" % (int(m.group(1)) / 100.0)
					self.properties["line-height"] = line_height

				break_before = el.attrib.get("fo:break-before")
				if break_before is not None:
					self.break_before = break_before
					# Webkit uses non-standard attribute
					if break_before == "column":
						self.properties["-webkit-column-break-before"] = "always"

				border = el.attrib.get("fo:border")
				if border is not None:
					self.properties["border"] = border

			# Text in blocks or inline
			# ODF 1.3 - 16.29.29
			elif el.tag == "style:text-properties":
				if opts.font_support_level >= 1:
					font_name = el.attrib.get("style:font-name")
					if font_name is not None:
						font_face_declaration = fonts[font_name]
						self.properties["font-family"] = font_face_declaration.get_css(opts.font_support_level)

				# Stash language in CSS object
				language = el.attrib.get("fo:language")
				if language is not None:
					self.language = language

				color = el.attrib.get("fo:color")
				if color is not None:
					# Drop black except on spans since we believe it is just noise.
					if color != "#000000" or self.family == "text":
						self.properties["color"] = color

				# Not clear how this is different from background-color in paragraph-properties
				color = el.attrib.get("fo:background-color")
				if color is not None:
					if color != "transparent":
						self.properties["background-color"] = color

				for prop in ("font-size", "font-style", "font-weight"):
					value = el.attrib.get(f"fo:{prop}")
					if value is not None:
						self.properties[prop] = value

				text_position = el.attrib.get("style:text-position")
				if text_position is not None:
					m = re.match(r"^((super)|(sub)|(\d+%))( (\d+%))?$", text_position)
					if not m:
						raise OdfNotImplementedYet("unrecognized text position: %s" % text_position)
					vertical_align = m.group(1)
					font_scale = m.group(6)
					if font_scale is None:
						if vertical_align == "super" or vertical_align == "sub":
							font_scale = "60%"
					if vertical_align == "0%":
						print("  Warning: nested text-position in %s not converted correctly" % self.name)
					else:
						self.properties["vertical-align"] = vertical_align
						if font_scale is not None:
							self.properties["font-size"] = font_scale

				underline = el.attrib.get("style:text-underline-style","none")
				if underline != "none":
					self.properties["text-decoration"] = "underline"

				# FIXME: has side effect of canceling underlining
				line_through = el.attrib.get("style:text-line-through-style","none")
				if line_through != "none":
					self.properties["text-decoration"] = "line-through"

			elif el.tag == "style:table-properties":
				width = el.attrib.get("style:width")
				# If the table has a width wide enough to reach the likely margins,
				# assume the intent was to make it 100% wide.
				if dimension2points(width) > (6.5 * 72.0):
					self.properties["width"] = "100%"
					self.properties["clear"] = "both"
				# Otherwise, use the requested width, but make it the maxiumum
				# width so that the table can shrink in small displays.
				else:
					self.properties["max-width"] = width

				align = el.attrib.get("table:align")
				if align is not None:
					if align == "right":
						self.properties["margin-left"] = "auto"
					elif align == "center":
						self.properties["margin-left"] = "auto"
						self.properties["margin-right"] = "auto"

			elif el.tag == "style:table-column-properties":
				column_width = el.attrib.get("style:column-width")
				if column_width is not None:
					self.properties["width"] = column_width

			elif el.tag == "style:table-row-properties":
				min_row_height = el.attrib.get("style:min-row-height")
				if min_row_height is not None:
					self.properties["height"] = min_row_height

			if el.tag == "style:table-cell-properties":
				vertical_align = el.attrib.get("style:vertical-align","top")
				if vertical_align == "middle" or vertical_align == "bottom":
					self.properties["vertical-align"] = vertical_align

			if el.tag == "style:graphic-properties":
				if el.attrib.get("style:vertical-rel") == "baseline":
					pass
				else:
					horizontal_pos = el.attrib.get("style:horizontal-pos")
					if horizontal_pos in ("left", "right"):
						self.properties["float"] = horizontal_pos
						self.properties["clear"] = horizontal_pos
					elif horizontal_pos == "from-left":
						self.properties["float"] = "left"
						self.properties["clear"] = "left"
					elif horizontal_pos == "center":
						self.properties["display"] = "block"
						self.properties["margin-left"] = "auto"
						self.properties["margin-right"] = "auto"
				if el.attrib.get("style:mirror") == "horizontal":
					self.properties["transform"] = "scaleX(-1)"
				# Without this, links will get tangled with the links of the parallel paragraph.
				# Why does not seem to be well-understood.
				if "float" in self.properties:
					self.properties["position"] = "relative"
					self.properties["z-index"] = "1"

		# FIXME: read up on this. Does this attribute really indicate a new page?
		# NOTE: this will override the break-before in <paragraph-properties>
		if "style:master-page-name" in odt_style.attrib and odt_style.attrib["style:master-page-name"] != "":
			self.break_before = "page"

		# If we are simplifying table cell borders, make all four borders the
		# same by picking the last one listed which is not "none".
		if self.family == "table-cell" and opts.simplify_table_borders:
			for name, value in list(self.properties.items()):
				if name.startswith("border-"):
					del self.properties[name]
					if value != "none":
						self.properties["border"] = value
			if "vertical-align" not in self.properties:
				self.simplified_td = True

class TableCellStyle(Style):
	def __init__(self, odt_style:ET._Element, parent:BaseStyle|None, fonts:FontFaces, opts:Odt2HtmlConfig):
		super().__init__(odt_style, parent, fonts, opts)
		self.is_th = False

	@property
	def className(self):
		if self.simplified_td:
			# drop the cell part of the name
			return self.name.split(".")[0].replace("_20_","_")
		return super().className

	def get_template(self) -> str:
		if self.template != "__AUTO__":
			return self.template
		elif self.simplified_td:
			if self.is_th:
				return "TABLE.%s TH"
			else:
				return "TABLE.%s TD"
		else:
			if self.is_th:
				return "TH.%s"
			else:
				return "TD.%s"

class ListStyle(BaseStyle):
	"""Represents an ODF list style rule"""
	def __init__(self, odt_style:ET._Element):
		assert odt_style.tag == "text:list-style"
		name = odt_style.attrib["style:name"]
		super().__init__("list", name, None, "UL.%s")
		self.levels = []
		self.ordered = False
		previous_margin_left = 0.0
		for el in odt_style:
			if el.tag == "text:list-level-style-bullet":
				pass
			elif el.tag == "text:list-level-style-number":
				self.template = "OL.%s"
				self.ordered = True
			else:
				raise OdfNotImplementedYet("Unsupported list-style element: %s" % el.tag)

			level = int(el.attrib["text:level"])
			for el2 in el:
				if el2.tag == "style:list-level-properties":
					for el3 in el2:
						# FIXME: text:label-followed-by
						if el3.tag == "style:list-level-label-alignment" and el3.attrib.get("text:label-followed-by") == "listtab":
							margin_left = dimension2points(el3.attrib["fo:margin-left"])
							self.add_level(level, "%.2fpt" % (margin_left - previous_margin_left))
							previous_margin_left = margin_left
							break
					else:		# presumably "space"
						self.add_level(level, "18pt")
						previous_margin_left += 18
					break
			else:
				OdfInvalid("list-style %s has not list-level-properties" % self.name)

	def add_level(self, level:int, indentation):
		self.levels.append(indentation)
		assert len(self.levels) == level, "Incorrect levels in list style %s" % self.name

	def __str__(self):
		return self.template % self.name + ", ".join(self.levels)

	def get_css(self, css_version):
		css_text = []
		css_text.append((self.template % self.name) + " LI{margin-left:0;text-indent:0}")
		count = 0
		for level in self.levels:
			css_text.append(self.template % self.name + (" " + self.template.split(".")[0]) * count + "{padding-left:%s}" % level)
			count += 1
		return "\n".join(css_text)

class Styles(UserDict):
	"""Container for styles from the ODT document"""

	def __init__(self, opts:Odt2HtmlConfig):
		super().__init__()
		self.opts = opts

		self.default_language = None	# to set on <HTML> tag
		self.fonts = FontFaces()
		self.byname:dict[str,BaseStyle] = {}			# by name from ODT file
		self.claims:dict[ET._Element,BaseStyle] = {}
		self.plugin_rules:list[str] = []			# lines we plugins have asked us to add to the stylesheet

	def load_font_face_decls(self, odt_font_face_decls:ET._Element) -> None:
		"""<font-face-decls> are passed to this function"""
		for font_face in odt_font_face_decls:
			assert font_face.tag == "style:font-face", font_face.tag
			font_face_obj = FontFace(font_face)
			self.fonts[font_face_obj.name] = font_face_obj

	def load_stylesheet(self, odt_stylesheet:ET._Element) -> None:
		"""Styles tags (of which there are several) are passed to this function"""
		if self.opts.debug:
			print("===== Converting ODF Stylesheet =====")

		# Make first pass.
		dependent = []
		for style in odt_stylesheet:
			if not self.on_tag(style, pass1=True):
				if self.opts.debug:
					print("    deferring loading")
				dependent.append(style)

		# Make a second pass to convert styles which had unresolved dependencies.
		for style in dependent:
			self.on_tag(style, pass1=False)

	def on_tag(self, odt_style:ET._Element, pass1:bool) -> bool:
		"""Load a style tag and its children. Return true if all dependencies have been met."""
		if self.opts.debug:
			print("  <%s %s>" % (
				odt_style.tag,
				"\n      ".join([f"{name}={repr(value)}" for name, value in odt_style.attrib.items()])
				))
		if odt_style.tag == "style:default-style":
			return self.on_tag_default_style(odt_style)
		if odt_style.tag == "style:style":
			return self.on_tag_style(odt_style, pass1)
		if odt_style.tag == "text:list-style":
			return self.on_tag_list_style(odt_style)
		if self.opts.debug:
			print("    unimplemented style tag: %s" % odt_style.tag)
		return True

	def on_tag_default_style(self, odt_style:ET._Element) -> bool:
		"""Partial implementation of <style:default-style>"""
		assert odt_style.tag == "style:default-style"

		# FIXME: mostly unimplemented
		# <style:default-style style:family="paragraph">
		#  <style:paragraph-properties fo:hyphenation-ladder-count="no-limit" style:text-autospace="ideograph-alpha" style:punctuation-wrap="hanging" sty
		#  <style:text-properties style:use-window-font-color="true" style:font-name="Liberation Serif" fo:font-size="12pt" fo:language="en" fo:country="US"
		# </style:default-style>
		if odt_style.attrib["style:family"] == "paragraph":
			for el in odt_style:
				if el.tag == "style:text-properties":
					self.default_language = el.attrib.get("fo:language")
					self.default_font_family = el.attrib["style:font-name"]

		return True

	def on_tag_style(self, odt_style:ET._Element, pass1:bool) -> bool:
		"""Implementation of <style:style>"""
		assert odt_style.tag == "style:style"
		family = odt_style.attrib["style:family"]

		parent_style = None
		parent_style_name = odt_style.attrib.get("style:parent-style-name")
		if parent_style_name is not None:
			parent_style = self.get((family, parent_style_name))
			if parent_style is None:
				if pass1:
					return False
				else:
					#raise OdfInvalid("missing parent of: %s %s" % (style.tag, style.attrib))
					print(f"Warning: style wants parent: {odt_style.tag} {odt_style.attrib}")

		if family == "table-cell":
			style = TableCellStyle(odt_style, parent_style, self.fonts, self.opts)
		else:
			style = Style(odt_style, parent_style, self.fonts, self.opts)

		if self.opts.debug:
			print("    CSS: %s" % style.get_css(3.0).replace("\n","\n         "))
		self[(style.family, style.name)] = style
		self.byname[style.name] = style
		return True

	def on_tag_list_style(self, odt_style:ET._Element) -> bool:
		"""Partial implementation <text:list-style>"""
		style = ListStyle(odt_style)
		if self.opts.debug:
			print("    CSS: %s" % style.get_css(3.0).replace("\n","\n         "))
		self[("list", style.name)] = style
		self.byname[style.name] = style
		return True

	def claim_style(self, odt_el, html_el, style_name:str) -> BaseStyle|None:
		"""
		The HTML generator calls this when it emits an element which uses a style.
		We set the used flag, and the caller gets the style.
		"""
		if style_name not in self.byname:
			#raise OdfInvalid(f"A {odt_el.tag} uses undefined style \"{style_name}\"")
			print(f"Warning: A {odt_el.tag} uses undefined style \"{style_name}\"")
			return None
		style = self.byname[style_name]
		style.used = True
		self.claims[html_el] = style
		return style

	# The base stylesheet for web browers
	# TODO: When we improve the style converter, we may be able to cut this down.
	base_style = textwrap.dedent("""\
		@media print { @page { margin: 0.5in } }
		HTML,BODY,H1,H2,H3,H4,H4,P,OL,UL,LI { margin:0; padding:0 }
		BODY { font-size:12pt }
		H1,H2,H3,H4,H5 { font-size: inherit }
		UL,OL { list-style-position: outside }
		HR.pagebreak { margin: 0.5in }
		SPAN.space { white-space: pre-wrap }

		TABLE { border-collapse: collapse }
		TH,TD { vertical-align: top }
		DIV.restrain { max-width: 100%; overflow-x: auto }

		.frame { background-color: white }
		SPAN.frame { display: inline-block; float: none }

		/* hack to join borders of adjacent paragraphs of a block quote */
		P.Quotations {
			background-color: white;
			}
		P.Quotations + P.Quotations {
			padding-top: 4pt;
			margin-top: -4pt;
			border-top: none;
			}

		/* Endnotes */
		A.note-citation { font-size: 65%; vertical-align: super; line-height: 0 }
		UL.notes { list-style-type: none; overflow-x: auto }
		LI.note { margin: .2em 0 }
		LI.note > DIV.note-citation { float: left; font-size: 10pt; width: 1.7em }
		LI.note > DIV.note-citation A { text-decoration: none; }
		LI.note > DIV.note-body > * { text-indent: 0; margin-left: 0 } !important

		DIV.footer { margin-top: 0.2in; font-size: 8pt; white-space: nowrap; max-width: 100%; overflow: hidden }
		@media screen {		/* push down footer */
			HTML { height:100% }
			BODY { position:relative; box-sizing:border-box; min-height:100%; margin:0 3%; padding:0.3in 0 0.4in }
			DIV.footer { position:absolute; left:0; bottom:0.1in; margin:0; }
			}
		""")

	def get_css(self, css_version):
		"""Return document styles converted to CSS"""
		rules = []

		# TODO: font level 1 should not set family
		if self.opts.font_support_level >= 2 and self.default_font_family is not None:
			font_family = "'{font_family}',serif".format(font_family=self.default_font_family)
		else:
			font_family = "serif"
		rules.append("BODY {font-family: %s}" % font_family)

		dedup = set()	# border simplification creates dups
		for css_style in self.values():
			if css_style.used or (not self.opts.drop_unused_styles):
				css = css_style.get_css(css_version)
				if css not in dedup:
					rules.append(css)
					dedup.add(css)

		return self.base_style + ("\n".join(self.plugin_rules)) + ("\n".join(rules))
