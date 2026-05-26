"""
These classes take ODF stylesheets and convert them to CSS stylesheets.
"""

import re
import fnmatch
import textwrap
from collections import UserDict

import lxml.etree as ET

from odt2html.console import Console
from odt2html.exceptions import OdfNotImplementedYet, OdfInvalid
from odt2html.config import Odt2HtmlConfig
from odt2html.utils import normalize_dimensions, dimension2points

class FontFace:
	"""Description of a font face and info for substitution"""

	def __init__(self, font_face:ET._Element):
		assert font_face.tag == "style:font-face"
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
		"""Convert this font-face """

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
	"""Font face lookup"""

class StylePropertiesBase:
	"""Base class for <style:*-properites>"""
	def __init__(self, style_el:ET._Element, attrib:dict, fonts:FontFaces, opts:Odt2HtmlConfig, console:Console):
		self.attrib = attrib
		self.fonts = fonts
		self.opts = opts
		self.console = console
		self.parent = None
		self.init(style_el)
	def init(self, style_el:ET._Element):
		pass
	def get_attrib(self, name:str, default:str|None=None):
		"""Retrieve a style attribute extending the search to parents and grandparents"""
		props = self
		while props is not None:
			value = props.attrib.get(name)
			if value is not None:
				return value
			props = props.parent
		return default
	def get_properties(self, css_version:float) -> dict:
		"""Produce a dict() of CSS properties to set"""
		raise NotImplementedError

class BlockStyleProperties(StylePropertiesBase):
	"""Properties of sections, paragraphs, etc."""
	def subsumable(self):
		"""Test whether the blocks attributes may simply be transfered to its parent"""
		props = self
		while props is not None:
			for pattern in ("fo:margin*", "fo:border*"):
				if len(fnmatch.filter(props.attrib.keys(), pattern)) > 0:
					return False
			props = props.parent
		return True
	def get_properties(self, css_version:float) -> dict:
		properties = {}
		for prop in (
				"margin", "margin-left", "margin-right", "margin-top", "margin-bottom",
				"padding", "padding-left", "padding-right", "padding-top", "padding-bottom",
				"border", "border-left", "border-right", "border-top", "border-bottom",
			):
			value = self.get_attrib(f"fo:{prop}")
			if value is not None:
				if value != "100%":	# don't know what 100% is supposed to mean, but it is poison...
					properties[prop] = normalize_dimensions(prop, value)
		return properties

class GraphicStyleProperties(BlockStyleProperties):
	@property
	def clear(self):
		# FIXME: Make sure this is set only when clear will actually be issued below.
		return self.get_attrib("style:horizontal-pos") in ("left", "right", "from-left")

	def get_properties(self, css_version:float) -> dict:
		properties = {}
		if self.get_attrib("style:vertical-rel") == "baseline":
			pass
		else:
			horizontal_pos = self.get_attrib("style:horizontal-pos")
			if horizontal_pos in ("left", "right"):
				properties["float"] = horizontal_pos
				properties["clear"] = horizontal_pos
			elif horizontal_pos == "from-left":
				properties["float"] = "left"
				properties["clear"] = "left"
			elif horizontal_pos == "center":
				properties["display"] = "block"
				properties["margin-left"] = "auto"
				properties["margin-right"] = "auto"
		if self.get_attrib("style:mirror") == "horizontal":
			properties["transform"] = "scaleX(-1)"
		# Without this, links will get tangled with the links of the parallel paragraph.
		# Why does not seem to be well-understood.
		if "float" in properties:
			properties["position"] = "relative"
			properties["z-index"] = "1"
		return properties

class ParagraphStyleProperties(BlockStyleProperties):
	"""<style:paragraph-properties>"""
	def get_properties(self, css_version:float) -> dict:
		properties = {}
		for prop in ("text-align", "text-indent", "background-color"):
			value = self.get_attrib(f"fo:{prop}")
			if value is not None:
				properties[prop] = value

		line_height = self.get_attrib("fo:line-height")
		if line_height is not None:
			# Convert percentage line height to multiplication factor because percentage
			# line height is inherited differently in ODF and in CSS.
			m = re.match(r"^(\d+)%$", line_height)
			if m:
				line_height = "%.2f" % (int(m.group(1)) / 100.0)
			properties["line-height"] = line_height

		break_before = self.get_attrib("fo:break-before")
		if break_before is not None:
			self.break_before = break_before
			# Webkit uses non-standard attribute
			if break_before == "column":
				properties["-webkit-column-break-before"] = "always"

		border = self.get_attrib("fo:border")
		if border is not None:
			properties["border"] = border

		return properties

class SectionStyleProperties(BlockStyleProperties):
	"""<style:section-properties>"""
	def init(self, style_el:ET._Element):
		self.column_count = None
		self.column_gap = None
		for child in style_el:
			if child.tag == "style:columns":
				self.column_count = child.attrib.get("fo:column-count")
				self.column_gap = child.attrib.get("fo:column-gap")
		self.clear = self.column_count is not None or self.column_gap is not None

	def get_properties(self, css_version:float) -> dict:
		properties = super().get_properties(css_version)
		for prop, value in (
				("column-count", self.column_count),
				("column-gap", self.column_gap)
				):
			if value is not None:
				properties["@media"] = "(min-width:8in)"
				properties[prop] = value
				properties["-webkit-%s" % prop] = value
				properties["-moz-%s" % prop] = value
		if self.clear:
			properties["clear"] = "both"		# looks better this way
		return properties

class TableStyleProperties(BlockStyleProperties):
	"""<style:table-properties>"""
	def init(self, style_el:ET._Element):
		self.clear = dimension2points(self.get_attrib("style:width","0")) > (6.5 * 72.0)

	def get_properties(self, css_version:float) -> dict:
		properties = {}
		width = self.get_attrib("style:width")
		# If the table has a width wide enough to reach the likely margins,
		# assume the intent was to make it 100% wide.
		if self.clear:
			properties["width"] = "100%"
			properties["clear"] = "both"
		# Otherwise, use the requested width, but make it the maxiumum
		# width so that the table can shrink in small displays.
		else:
			properties["max-width"] = width

		align = self.get_attrib("table:align")
		if align is not None:
			if align == "right":
				properties["margin-left"] = "auto"
			elif align == "center":
				properties["margin-left"] = "auto"
				properties["margin-right"] = "auto"

		return properties

class TableColumnProperties(BlockStyleProperties):
	"""<style:table-column-properties>"""
	def get_properties(self, css_version:float) -> dict:
		properties = {}
		column_width = self.get_attrib("style:column-width")
		if column_width is not None:
			properties["width"] = column_width
		return properties

class TableRowProperties(BlockStyleProperties):
	"""<style:table-row-properties>"""
	def get_properties(self, css_version:float) -> dict:
		properties = {}
		min_row_height = self.get_attrib("style:min-row-height")
		if min_row_height is not None:
			properties["height"] = min_row_height
		return properties

class TableCellProperties(BlockStyleProperties):
	"""<style:table-cell-properties>"""
	def init(self, style_el:ET._Element):
		self.simplified_away = False
		self.border = None

		# If we are simplifying table cell borders, make all four borders the
		# same by picking the last one listed which is not "none".
		#
		# FIXME: This does not follow the style inheritance chain. As of May 2026
		# Libreoffice does not use style inheritance in tables.
		if self.opts.simplify_table_borders:
			for name, value in list(self.attrib.items()):
				if name.startswith("fo:border-"):
					if value != "none":
						self.border = value
			assert self.border is not None

			# If simplifying and no vertical align, may be omitted entirely
			vertical_align = self.get_attrib("style:vertical-align")
			if vertical_align is None:
				self.simplified_away = True

	def get_properties(self, css_version:float) -> dict:
		properties = super().get_properties(css_version)
		vertical_align = self.get_attrib("style:vertical-align","top")
		if vertical_align == "middle" or vertical_align == "bottom":
			properties["vertical-align"] = vertical_align
		if self.opts.simplify_table_borders:
			for name, value in list(properties.items()):
				if name.startswith("border-"):
					del properties[name]
			properties["border"] = self.border
		return properties

class TextStyleProperties(StylePropertiesBase):
	def get_properties(self, css_version:float) -> dict:
		properties = {}
		if self.opts.font_support_level >= 1:
			font_name = self.get_attrib("style:font-name")
			if font_name is not None:
				font_face_declaration = self.fonts[font_name]
				properties["font-family"] = font_face_declaration.get_css(self.opts.font_support_level)

		# Stash language in CSS object
		language = self.get_attrib("fo:language")
		if language is not None:
			self.language = language

		color = self.get_attrib("fo:color")
		if color is not None:
			# Drop black except on spans since we believe it is just noise.
			#if color != "#000000" or self.family == "text":
			if color != "#000000":
				properties["color"] = color

		# Not clear how this is different from background-color in paragraph-properties
		color = self.get_attrib("fo:background-color")
		if color is not None:
			if color != "transparent":
				properties["background-color"] = color

		for prop in ("font-size", "font-style", "font-weight"):
			value = self.get_attrib(f"fo:{prop}")
			if value is not None:
				properties[prop] = value

		text_position = self.get_attrib("style:text-position")
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
				self.console.warning("nested text-position not converted correctly", indent=2)
			else:
				properties["vertical-align"] = vertical_align
				if font_scale is not None:
					properties["font-size"] = font_scale

		underline = self.get_attrib("style:text-underline-style","none")
		if underline != "none":
			properties["text-decoration"] = "underline"

		# FIXME: has side effect of canceling underlining
		line_through = self.get_attrib("style:text-line-through-style","none")
		if line_through != "none":
			properties["text-decoration"] = "line-through"

		return properties

class StyleBase:
	"""Represents an ODF style rule"""
	def __init__(self, odt_style:ET._Element, family:str, template:str):
		self.family = family
		self.name:str = odt_style.attrib["style:name"]
		self.parent_name = odt_style.attrib.get("style:parent-style-name")
		self.parent = None
		self.template:str = template	# printf()-style template
		self.used = False				# mentioned in document?
		self.tag_override = None		# change <p> or <span> to this
		self.break_before = None		# "page" for page break before
		self.language = None			# not CSS, but where else can we put this?
		self.simplified_away = False
		self.clear = False
		self.text_properties = None
		self.block_properties = None
		self.graphic_properties = None

		tag_override = {
			("text", "Emphasis"): "i",			# <em> would also be appropriate
			("text", "Strong_20_Emphasis"): "b",
			("paragraph", "Quotations"): "blockquote",
			}.get((self.family, self.name))
		if tag_override is not None:
			self.tag_override = tag_override
			self.template = tag_override.upper() + ".%s"

	def __str__(self):
		return f"<Style family={repr(self.family)} name={repr(self.name)}>"

	def set_parent(self, parent):
		self.parent = parent
		self.break_before = parent.break_before
		self.language = parent.language

	@property
	def className(self):
		"""ODF style nameconverted to legal CSS class name"""
		return self.name.replace(".","_").replace("_20_","_")

	def get_template(self):
		return self.template

	def is_instance_of(self, class_name:str):
		style = self
		while style is not None:
			if style.name == class_name:
				return True
			style = style.parent
		return False

	def get_css(self, css_version:float) -> str:
		raise NotImplementedError

class Style(StyleBase):
	"""Represents <style:style>, but not <text:list-style>"""
	def __init__(self, odt_style:ET._Element, fonts:FontFaces, opts:Odt2HtmlConfig, console:Console):
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

		super().__init__(odt_style, family, template)

		for style_child in odt_style:
			if opts.debug:
				print("    <%s %s>" % (
					style_child.tag,
					"\n        ".join([f"{name}={repr(value)}" for name, value in style_child.attrib.items()])
					))
			match style_child.tag:
				case "style:graphic-properties":
					self.graphic_properties = GraphicStyleProperties(style_child, style_child.attrib, fonts, opts, console)
				case "style:paragraph-properties":
					self.block_properties = ParagraphStyleProperties(style_child, style_child.attrib, fonts, opts, console)
				case "style:section-properties":
					self.block_properties = SectionStyleProperties(style_child, style_child.attrib, fonts, opts, console)
				case "style:table-properties":
					self.block_properties = TableStyleProperties(style_child, style_child.attrib, fonts, opts, console)
				case "style:table-column-properties":
					self.block_properties = TableColumnProperties(style_child, style_child.attrib, fonts, opts, console)
				case "style:table-row-properties":
					self.block_properties = TableRowProperties(style_child, style_child.attrib, fonts, opts, console)
				case "style:table-cell-properties":
					self.block_properties = TableCellProperties(style_child, style_child.attrib, fonts, opts, console)
				case "style:text-properties":
					self.text_properties = TextStyleProperties(style_child, style_child.attrib, fonts, opts, console)
				case _:
					if opts.debug:
						print("      Unimplemented style child: %s" % style_child.tag)

		# Guarantee the presence of these properties objects in order to preserve the inheritance chain
		if self.graphic_properties is None:
			self.graphic_properties = GraphicStyleProperties([], {}, fonts, opts, console)
		if self.block_properties is None:
			self.block_properties = BlockStyleProperties([], {}, fonts, opts, console)
		if self.text_properties is None:
			self.text_properties = TextStyleProperties([], {}, fonts, opts, console)

		# FIXME: read up on this. Does this attribute really indicate a new page?
		# NOTE: this will override the break-before in <paragraph-properties>
		if "style:master-page-name" in odt_style.attrib and odt_style.attrib["style:master-page-name"] != "":
			self.break_before = "page"

	def get_properties(self, css_version:float):
		properties = {}
		properties.update(self.graphic_properties.get_properties(css_version))
		properties.update(self.block_properties.get_properties(css_version))
		properties.update(self.text_properties.get_properties(css_version))
		return properties

	def get_css(self, css_version:float) -> str:
		"""Return a CSS rule representing this style"""
		properties = self.get_properties(css_version)
		media = properties.get("@media")
		if media:
			del properties["@media"]
		style_text = "%s{%s}" % (
			self.get_template() % self.className,
			";".join(["%s:%s" % (name, value) for name, value in properties.items()])
			)
		if media is not None and css_version >= 3.0:
			style_text = "@media %s { %s }" % (
				media,
				style_text
				)
		return style_text

class TableCellStyle(Style):
	"""Represents <style:style style:family='table-cell'"""
	def __init__(self, odt_style:ET._Element, fonts:FontFaces, opts:Odt2HtmlConfig, console:Console):
		super().__init__(odt_style, fonts, opts, console)
		self.is_th = False

	@property
	def className(self):
		if self.simplified_away:
			# drop the cell part of the name
			return self.name.split(".")[0].replace("_20_","_")
		return super().className

	def get_template(self) -> str:
		if self.template != "__AUTO__":
			return self.template
		elif self.simplified_away:
			if self.is_th:
				return "TABLE.%s TH"
			else:
				return "TABLE.%s TD"
		else:
			if self.is_th:
				return "TH.%s"
			else:
				return "TD.%s"

class ListStyle(StyleBase):
	"""Represents an ODF list style rule"""
	def __init__(self, odt_style:ET._Element):
		assert odt_style.tag == "text:list-style"
		super().__init__(odt_style, "list", "UL.%s")

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

	def get_css(self, css_version) -> str:
		css_text = []
		css_text.append((self.template % self.name) + " LI{margin-left:0;text-indent:0}")
		count = 0
		for level in self.levels:
			css_text.append(self.template % self.name + (" " + self.template.split(".")[0]) * count + "{padding-left:%s}" % level)
			count += 1
		return "\n".join(css_text)

class Styles(UserDict):
	"""Container for styles from the ODT document"""

	def __init__(self, opts:Odt2HtmlConfig, console:Console):
		super().__init__()
		self.opts = opts
		self.console = console

		self.default_language = None	# to set on <HTML> tag
		self.fonts = FontFaces()
		self.byname:dict[str,StyleBase] = {}			# by name from ODT file
		self.claims:dict[ET._Element,StyleBase] = {}

		# lines we plugins have asked us to add to the stylesheet
		self.plugin_rules:list[str] = []

	def load_font_face_decls(self, odt_font_face_decls:ET._Element) -> None:
		"""<font-face-decls> are passed to this function"""
		for font_face in odt_font_face_decls:
			assert font_face.tag == "style:font-face", font_face.tag
			font_face_obj = FontFace(font_face)
			self.fonts[font_face_obj.name] = font_face_obj

	def load_stylesheet(self, odt_stylesheet:ET._Element) -> None:
		"""Styles tags (of which there are several) are passed to this function"""
		if self.opts.debug:
			#print("===== Converting ODF Stylesheet =====")
			self.console.banner("Converting ODF Stylesheet", indent=2)
		for odt_style in odt_stylesheet:
			if self.opts.debug:
				print("  <%s %s>" % (
					odt_style.tag,
					"\n      ".join([f"{name}={repr(value)}" for name, value in odt_style.attrib.items()])
					))
			match odt_style.tag:
				case "style:default-style":
					self.on_tag_default_style(odt_style)
				case "style:style":
					self.on_tag_style(odt_style)
				case "text:list-style":
					self.on_tag_list_style(odt_style)
				case _:
					#raise OdfNotImplementedYet(f"style tag: {odt_style.tag}")
					if self.opts.debug:
						print(f"    unimplemented style tag: {odt_style.tag}")

	def connect_styles(self):
		"""Call after last call to load_stylesheet() to connect children to parents"""
		if self.opts.debug:
			self.console.banner("Connecting styles to parents", indent=2)
		for style in self.values():
			if style.parent_name is not None:
				try:
					parent = self[(style.family, style.parent_name)]
					if self.opts.debug:
						print(f"  {style} to parent {parent}")
					style.set_parent(parent)
				except KeyError:
					if style.parent_name in ("Header","Footer"):		# FIXME: Why is this missing?
						self.console.warning(f"\"{style.family}:{style.name}\" has non-existent parent \"{style.parent_name}\"")
					else:
						raise OdfInvalid(f"Style \"{style.family}:{style.name}\" has non-existent parent \"{style.parent_name}\"")

	def on_tag_default_style(self, odt_style:ET._Element) -> None:
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

	def on_tag_style(self, odt_style:ET._Element) -> None:
		"""Implementation of <style:style>"""
		assert odt_style.tag == "style:style"
		family = odt_style.attrib["style:family"]

		if family == "table-cell":
			style = TableCellStyle(odt_style, self.fonts, self.opts, self.console)
		else:
			style = Style(odt_style, self.fonts, self.opts, self.console)

		if self.opts.debug:
			print("    CSS: %s" % style.get_css(3.0).replace("\n","\n         "))
		self[(style.family, style.name)] = style
		self.byname[style.name] = style

	def on_tag_list_style(self, odt_style:ET._Element) -> None:
		"""Partial implementation <text:list-style>"""
		style = ListStyle(odt_style)
		if self.opts.debug:
			print("    CSS: %s" % style.get_css(3.0).replace("\n","\n         "))
		self[("list", style.name)] = style
		self.byname[style.name] = style

	def claim_style(self, odt_el, html_el, style_name:str) -> StyleBase|None:
		"""
		The HTML generator calls this when it emits an element which uses a style.
		We set the used flag, and the caller gets the style.
		"""
		if style_name not in self.byname:
			#raise OdfInvalid(f"{odt_el.tag} uses non-existent style \"{style_name}\"")
			self.console.warning(f"{odt_el.tag} uses non-existent style \"{style_name}\"", indent=2)
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

	def get_css(self, css_version) -> str:
		"""Return all used document styles converted to CSS"""
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
