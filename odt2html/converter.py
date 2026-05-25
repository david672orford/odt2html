import os
import zipfile
import json
import re
from copy import deepcopy

import lxml.etree as ET
from lxml.builder import E

from rcssmin import cssmin
from rjsmin import jsmin

from odt2html.config import Odt2HtmlConfig
from odt2html.parser import make_odf_parser
from odt2html.utils import element_empty, element_extract_text, href_to_html
from odt2html.exceptions import OdfInvalid, OdfNotSupported, OdfNotImplementedYet, OdfBadFormatting
from odt2html.images import Odt2HtmlImages
from odt2html.hyperlinks import HyperlinkConverter
from odt2html.styles import Styles, TableCellStyle
from odt2html.tdsound import TDSound
from odt2html.wrapped_tables import WrappedTables
from odt2html.template import HtmlTemplate
from odt2html.metadata import HtmlMetadata
from odt2html.linter import Linter
from odt2html.epub import EpubWriter
from odt2html.graphics import convert_custom_shape, convert_rect, convert_line

class Odt2Html:
	"""This does the actual conversion from ODT to HTML"""
	def __init__(self, odt_filename:str, output_filename:str, opts:Odt2HtmlConfig|None=None):
		self.odt_filename:str = odt_filename
		self.output_filename:str = output_filename
		self.opts:Odt2HtmlConfig = opts if opts else Odt2HtmlConfig()

		self.output_dirname:str = os.path.dirname(output_filename)
		if self.output_dirname == "":
			self.output_dirname = "."

		self.subdocs_by_href = {}	# sections which represent child documents
		self.h1s = []				# level 1 headings
		self.topic_index_counter = 0

		# Create HTML objects into which we can start
		# to insert objects to represent the output document
		self.html_head:ET._Element = E.head()
		self.html_head.append(E.meta({"http-equiv":"content-type","content":"text/html; charset=utf-8"}))
		self.html_body:ET._Element = E.body()

		self.dirindex_entry = self.opts.dirindexes.find_entry(output_filename)

		self.open_odt()
		self.styles = self.load_styles()
		self.metadata = self.load_metadata()
		self.images = Odt2HtmlImages(self)
		self.hyperlinks = HyperlinkConverter(self)

		self.title_el = E.title(self.metadata["title"])
		self.html_head.append(self.title_el)

		if self.opts.output_format == "epub":
			self.opts.use_data_urls = False
			self.opts.keep_toc = False
			self.opts.split_by_sections = True
			#self.opts.svg2png = True

		self.run_conversion()

		if self.opts.warnings_formatting:
			Linter(self).warnings_formatting()

		if self.opts.output_format == "html":

			# Run post-processing plugins
			if "TD Sound" in self.metadata:
				TDSound(self).run()
			if self.opts.wrap_box_tables:
				WrappedTables(self).run()
			if self.opts.site_url is not None:
				HtmlMetadata(self).run()
			if self.opts.template:
				HtmlTemplate(self).run()

			# Link to code needed to display hyperlined media files
			self.hyperlinks.run()

			# Embed stylesheet (This must come after plugins)
			self.html_head.append(E.meta({"name":"viewport","content":"width=device-width,initial-scale=1"}))
			self.add_css(self.styles.get_css(3.0))

			# Compress JS and CSS
			if self.opts.minimize_resources:
				self.minimize_resources()

			self.save_html(output_filename)

		elif self.opts.output_format == "epub":
			writer = EpubWriter(self)
			writer.save(output_filename)

		else:
			raise AssertionError("Unimplemented output format: %s" % self.opts.output_format)

	#------------------------------------------------------------------
	# Load the style and content XML files into memory and create most
	# of the output HTML document in memory.
	#------------------------------------------------------------------

	def open_odt(self):
		"""Open the ODT zip file and load its main XML components"""

		self.odt = zipfile.ZipFile(self.odt_filename)

		if self.opts.debug:
			print("===== ODT Zip File Contents =====")
			for resource_filename in self.odt.namelist():
				print("  %s" % resource_filename)
			print()

		self.odf_parser = make_odf_parser()

		# Uncompress and parse the XML streams which we need.
		self.styles_xml = self.load_xml("styles.xml")
		self.meta_xml = self.load_xml("meta.xml")
		self.content_xml = self.load_xml("content.xml")

	def load_xml(self, filename) -> ET._ElementTree:
		#if self.opts.debug:
		#	print("===== %s =====" % filename)

		with self.odt.open(filename) as fh:
			tree = ET.parse(fh, parser=self.odf_parser)

		root = tree.getroot()

		# Strip namespace URIs from tag and attribute names
		# TODO: Once everything is converted over to prefixes, we should be able to drop this.
		for el in root.iter():
			assert el.tag is not None

		#if self.opts.debug:
		#	print(ET.tostring(tree, pretty_print=True, encoding="unicode"))

		return root

	def load_styles(self):
		"""Load styles from styles.xml and content.xml"""

		# Container for styles
		styles = Styles(self.opts)

		# Load the font definitions from styles.xml and content.xml
		for font_face_decls in (
			self.styles_xml.xpath("/office:document-styles/office:font-face-decls")[0],
			self.content_xml.xpath("/office:document-content/office:font-face-decls")[0],
			):
			styles.load_font_face_decls(font_face_decls)

		# Parse the styles from styles.xml and content.xml
		for stylesheet in (
				# from stylesheet UI
				self.styles_xml.xpath("/office:document-styles/office:styles")[0],

				#
				self.styles_xml.xpath("/office:document-styles/office:automatic-styles")[0],

				#
				self.styles_xml.xpath("/office:document-styles/office:master-styles")[0],

				# from element format UI
				self.content_xml.xpath("/office:document-content/office:automatic-styles")[0]
				):
			styles.load_stylesheet(stylesheet)

		return styles

	def load_metadata(self):
		metadata = {}
		meta = self.meta_xml.xpath("/office:document-meta/office:meta")[0]

		# Search for the title of the document. Priority:
		# 1) Metadata
		# 2) Contents of level 1 heading
		titles = meta.xpath("./dc:title")
		if len(titles) > 0 and titles[0].text is not None:
			metadata["title"] = titles[0].text
		else:
			headings = self.content_xml.xpath("/office:document-content/office:body/office:text//text:h")
			if len(headings) > 0:
				metadata["title"] = element_extract_text(headings[0])
		if "title" not in metadata:
			raise OdfNotSupported("No document title")

		# Search for the description of the document
		subjects = meta.xpath("./dc:subject")
		if len(subjects) > 0 and subjects[0].text is not None:
			metadata["description"] = subjects[0].text

		# Search for the keywords of the document
		keywords = meta.xpath("./meta:keyword")
		if len(keywords) > 0:
			self.html_head.append(E.meta({
				"name": "keywords",
				"content": ",".join(map(lambda keyword: keyword.text, keywords))
				}))

		# Look for odt2html configuration items in the document user data.
		for variable in meta.xpath("./meta:user-defined"):
			name = variable.attrib.get("meta:name")
			metadata[name] = variable.text

		return metadata

	#------------------------------------------------------------------
	# Run all the passes
	#------------------------------------------------------------------

	def run_conversion(self):
		# Get a pointer to the ODT document body.
		odt_body = self.content_xml.xpath("/office:document-content/office:body/office:text")[0]

		# Pass 1
		self.section_count = 0
		for odt_el in odt_body:
			self.scan_odt_element(odt_el)

		# Pass 2: convert the document and append it to the HTML body
		self.section_count = 0
		for odt_el in odt_body:
			self.convert_element(odt_el, self.html_body, None)		# calls self recursively

		# Pass 3: post processing
		self.do_post_processing()

		# Convert the footer and add it to the body
		# FIXME: Move some of this into styles.py?
		odt_footer = self.styles_xml.xpath("/office:document-styles/office:master-styles/style:master-page[@style:name='Standard']/style:footer/text:p")
		if len(odt_footer) >= 1:
			html_footer = E.div({"class":"footer"})
			self.convert_element(odt_footer[0], html_footer, None)
			self.html_body.append(E.footer(html_footer))

	#------------------------------------------------------------------
	# Pass 1
	#------------------------------------------------------------------

	def scan_odt_element(self, odt_el:ET._Element):
		"""
		Collect the source file names of the subdocuments of a master document.
		We need this information in order to resolve links between subdocuments.
		"""
		if odt_el.tag == "section":
			section_id = self.get_section_id(odt_el)
			subdoc_href = self.get_section_source_href(odt_el)
			if subdoc_href is not None:
				self.subdocs_by_href[subdoc_href] = section_id

	def get_section_id(self, odt_el:ET._Element):
		assert odt_el.tag == "text:section"
		self.section_count += 1
		if "text:name" in odt_el.attrib:
			return odt_el.attrib["text:name"].replace(" ","_")
		else:
			return "topsect%d" % self.section_count

	def get_section_source_href(self, odt_el:ET._Element):
		"""
		If this section encloses a subdocument of a master document, return an
		href to the subdocument with the extension changed to ".html".
		"""
		assert odt_el.tag == "text:section"
		if odt_el.attrib.get("text:protected","false") != "true":
			return None
		section_sources = odt_el.xpath("./text:section-source")
		if len(section_sources) == 0:
			return None
		if len(section_sources) != 1:
			raise OdfInvalid("%d <text:section-source> elements" % len(section_sources))
		href = section_sources[0].attrib["xlink:href"]
		return href_to_html(href)

	#------------------------------------------------------------------
	# Pass 2
	#------------------------------------------------------------------

	# This function converts an ODT element to HTML and adds it to the
	# parent HTML element specified. It then calls itself on each child
	# of the ODT element with the newly created HTML element as the
	# target parent.
	def convert_element(self, odt_el:ET._Element, html_parent_el:ET._Element|None, list_style_name:str|None, depth:int=0):

		style_name = odt_el.attrib.get("text:style-name")
		convert_children = True					# by default, call self recursively on children

		if odt_el.tag == "text:section":		# TODO: <text:section>
			if self.opts.debug:
				print("  Section:", odt_el.attrib.get("text:name"))
			html_el:ET._Element = E.div()
			if depth == 0:						# if at master document level
				section_id = self.get_section_id(odt_el)
				subdoc_href = self.get_section_source_href(odt_el)
				if subdoc_href:					# if this is a child of a master document,
					#if self.section_count != self.subdocs_by_href[subdoc_href] != subdoc_id:
					if self.section_count != self.subdocs_by_href[subdoc_href] != section_id:
						raise OdfInvalid("Master document inconsistency")
				html_el.attrib["id"] = section_id
			else:
				html_el.attrib["id"] = odt_el.attrib["text:name"].replace(" ","_")
		elif odt_el.tag == "section-source":	# handled during pass 1
			html_el = None

		# Block elements
		elif odt_el.tag == "text:h":
			if self.opts.debug:
				print("=" * 75)
				print(f" Heading \"{style_name.replace("_20_"," ")}\": {repr(element_extract_text(odt_el))}")
				print("=" * 75)
			level = int(odt_el.attrib["text:outline-level"])
			html_el = E("h%d" % level)
			if level == 1:	# level 1 headings have ID's

				if style_name and style_name.startswith("P"):
					print("  Warning: level 1 heading with paragraph style: %s" % style_name)

				bookmarks = odt_el.xpath("./text:bookmark-start")
				if len(bookmarks) > 0:
					h_id = bookmarks[0].attrib["text:name"]
				else:
					h_id = "subh%d" % (len(self.h1s) + 1)
				h_filename = "content%d.html" % self.section_count
				h_text = element_extract_text(odt_el)
				html_el.attrib["id"] = h_id
				self.h1s.append((h_filename, h_id, h_text))
		elif odt_el.tag == "text:p":
			assert html_parent_el is not None
			# If this paragraph is the first one inside an <LI> tag, put everything
			# inside the <LI> instead since otherwise, if the paragraph is indented,
			# it will move away from the bullet.
			if html_parent_el.tag == "li" and element_empty(html_parent_el):
				html_el = html_parent_el
			else:
				html_el = E.p()

		# Inline elements
		elif odt_el.tag == "text:span":
			html_el = E.span()
			html_el.tail = ""					# <-- prevents newline with pretty_print=True
		elif odt_el.tag in ("text:a", "draw:a"):
			html_el = self.hyperlinks.convert(odt_el)
		elif odt_el.tag == "text:line-break":
			html_el = E.br()
		elif odt_el.tag == "text:soft-page-break":	# FIXME: read up on this
			html_el = ET.Comment("soft-page-break")
		elif odt_el.tag == "text:tab":
			if len(odt_el) != 0:
				raise OdfInvalid("<tab> should not have children")
			html_el = E.span({"class":"tab"})
			html_el.text = 8 * " "				# eight non-breaking spaces
		elif odt_el.tag == "text:s":
			if len(odt_el) != 0:
				raise OdfInvalid("<s> should not have children")
			count = int(odt_el.attrib.get("text:c","1"))
			if count == 1:
				html_el = E._dropme({"odt_tag":"s"})
				html_el.text = " "
			else:
				html_el = E.span({"class":"space"})
				count = int(count * 1.15)		# 1.15 is fudge
				html_el.text = count * " "
		elif odt_el.tag == "text:page-number":		# FIXME: what about the content (which is an actual page number)?
			html_el = ET.Comment("page-number")
		elif odt_el.tag == "text:date":				# FIXME: <text:date>?
			html_el = E.span()

		# Frames
		elif odt_el.tag == "draw:frame":
			style_name = odt_el.attrib.get("draw:style-name")
			html_el = self.convert_frame(odt_el)
			if html_el.tag == "img":			# If frame was simplified to an <img>,
				convert_children = False		# its children should be discarded.
		elif odt_el.tag == "draw:text-box":
			html_el = html_parent_el

		# Graphics
		elif odt_el.tag == "draw:custom-shape":
			html_el = convert_custom_shape(odt_el, self.opts.debug)
			convert_children = False
		elif odt_el.tag == "draw:rect":
			html_el = convert_rect(odt_el, self.opts.debug)
		elif odt_el.tag == "draw:line":
			html_el = convert_line(odt_el, self.opts.debug)

		# Tables
		elif odt_el.tag.startswith("table:"):
			style_name = odt_el.attrib.get("table:style-name")
			if odt_el.tag == "table:table":
				html_el = E.table()
			elif odt_el.tag == "table:table-column":
				html_el = E.col()
			elif odt_el.tag == "table:table-header-rows":
				html_el = E.thead()
			elif odt_el.tag == "table:table-row":
				html_el = E.tr()
			elif odt_el.tag == "table:table-cell":
				html_el = E.td()
				if "table:number-rows-spanned" in odt_el.attrib:
					html_el.attrib["rowspan"] = odt_el.attrib["table:number-rows-spanned"]
				if "table:number-columns-spanned" in odt_el.attrib:
					html_el.attrib["colspan"] = odt_el.attrib["table:number-columns-spanned"]
			elif odt_el.tag == "table:covered-table-cell":
				html_el = None						# don't convert
			else:
				raise OdfNotImplementedYet("unimplemented table tag: %s" % odt_el.tag)

		# Lists
		elif odt_el.tag == "text:list":
			if style_name:
				list_style_name = style_name
			if self.styles[("list", list_style_name)].ordered:
				html_el = E.ol()
			else:
				html_el = E.ul()
		elif odt_el.tag == "text:list-header":
			raise OdfNotImplementedYet("<text:list-header>")
		elif odt_el.tag == "text:list-item":
			html_el = E.li()

		# Table of contents
		elif odt_el.tag == "text:table-of-content":
			if self.opts.keep_toc:
				html_el = E.div({"id":"toc"})
			else:
				html_el = None					# don't convert
		elif odt_el.tag == "text:table-of-content-source":
			html_el = None

		# Topic index
		elif odt_el.tag == "text:alphabetical-index":
			html_el = E.div({"id":"index"})
		elif odt_el.tag == "text:alphabetical-index-source":
			html_el = None
		elif odt_el.tag == "text:alphabetical-index-mark":			# zero width index entry mark
			#print("  Index mark:", str(odt_el.attrib), odt_el.tail)
			html_el = self.convert_index_mark(odt_el)
		elif odt_el.tag == "text:alphabetical-index-mark-start":		# start of index entry span
			#print("  Index mark start:", str(odt_el.attrib), odt_el.tail)
			html_el = self.convert_index_mark(odt_el)
		elif odt_el.tag == "text:alphabetical-index-mark-end":		# end of entry span
			html_el = E._dropme({"odt_tag":odt_el.tag})

		# Bookmarks
		elif odt_el.tag == "text:bookmark":
			html_el = E.span({
				"id": odt_el.attrib["text:name"],
				"class": "bookmark",
				})
		elif odt_el.tag == "text:bookmark-start":
			html_el = E._dropme({"odt_tag":odt_el.tag})
		elif odt_el.tag == "text:bookmark-end":
			html_el = E._dropme({"odt_tag":odt_el.tag})

		elif odt_el.tag == "text:index-body":
			html_el = E.div()
		elif odt_el.tag == "text:index-title":
			html_el = E.div()

		# Variables
		elif odt_el.tag == "text:user-defined":
			html_el = E.span({"class":"user-defined"})	# class is not used
		elif odt_el.tag == "text:variable-decls":
			html_el = None	# drop children too
		elif odt_el.tag == "text:variable-set":
			html_el = E._dropme({"odt_tag":odt_el.tag})

		# User note
		elif odt_el.tag == "office:annotation":
			html_el = None
		elif odt_el.tag == "office:annotation-end":
			html_el = None

		# Forms not really implemented. All we do is draw a box for each control.
		elif odt_el.tag == "office:forms":
			html_el = None
		elif odt_el.tag == "draw:control":
			html_el = E.span(
				{"style":"border: thin solid black;display:inline-block;width:100%%;max-width:%s;height:%s" % (
					odt_el.attrib["svg:width"],
					odt_el.attrib["svg:height"]
					)}
				)

		# Turn footnotes into <LI> tags. We later move them to a <UL> at the end of
		# the document leaving an <A> tag in the text in the place of each.
		# FIXME: Handling of footnote style is a hack
		elif odt_el.tag.startswith("text:note"):
			#print(f"{odt_el.tag}: {odt_el.attrib}")
			if odt_el.tag == "text:note":
				html_el = E.li({"id": odt_el.attrib["text:id"], "class":"note"})
			elif odt_el.tag == "text:note-citation":
				html_el = E.div({"class":"note-citation"})
			elif odt_el.tag == "text:note-body":
				html_el = E.div({"class":"note-body"})
			else:
				raise OdfNotImplementedYet("unimplemented note tag: %s" % odt_el.tag)

		elif odt_el.tag == "text:sequence-decls":		# mystery
			html_el = None

		else:
			if self.opts.error_unimplemented_tags:
				raise OdfNotImplementedYet("unimplemented tag: %s" % odt_el.tag)
			print("  Warning: unimplemented tag: %s" % odt_el.tag)
			html_el = E.span()

		# If we converted the ODF element to an HTML element
		# (rather than simply dropping it),
		if html_el is not None:
			# Copy the internal and trailing text from the ODF element to the HTML element
			if odt_el.text is not None:
				html_el.text = odt_el.text
			if odt_el.tail is not None:
				html_el.tail = odt_el.tail

			if style_name is not None:
				style = self.styles.claim_style(odt_el, html_el, style_name)
				if style is not None:
					if not style.simplified_td:
						if "class" in html_el.attrib:
							html_el.attrib["class"] += (" " + style.className)
						else:
							html_el.attrib["class"] = style.className
					if style.language is not None:
						html_el.attrib["lang"] = style.language
					if style.tag_override is not None:
						html_el.tag = style.tag_override
					if style.break_before == "page":
						# This element should appear at the top of a new page.
						assert html_parent_el is not None
						if len(self.html_body) > 0 or len(html_parent_el) > 0:		# if not at top of first page,
							if len(html_parent_el):									# if parent already has content
								html_parent_el.append(E.hr({"class":"pagebreak"}))
							else:													# otherwise, try to get it above parent
								self.html_body.append(E.hr({"class":"pagebreak"}))

			if convert_children:
				self.convert_children(odt_el, html_el, list_style_name, depth)

			# Perform post processing which requires access to the children.
			if odt_el.tag == "text:p":
				if element_empty(html_el):	# In HTML 4 empty <p> tags are supposed to be ignored.
					html_el.append(E.br())	# Add a <br> so that doesn't happen.
			elif odt_el.tag == "table:table":
				html_el = self.table_fixup(html_el, html_parent_el)
			elif "frame" in html_el.attrib.get("class","").split():
				self.frame_fixup(html_el)

			# There are some empty ODF tags which we would like to drop, but we cannot
			# do so immediately since they come inside runs of text and we do
			# not want to lose their tail text. Here we merge their text and tail text
			# into either the parent element or the previous sibling element and then
			# drop them. We do this after convert_children() so we can assert it is empty.
			if html_el.tag == "_dropme":
				if self.opts.debug:
					print("Dropping %s" % html_el.attrib["odt_tag"])
				assert html_parent_el is not None
				if len(html_el) > 0:
					raise OdfInvalid("<%s> tag not empty" % html_el.attrib["odt_tag"])
				text = ""
				if html_el.text is not None:
					text += html_el.text
				if html_el.tail is not None:
					text += html_el.tail
				if text != "":
					if len(html_parent_el) == 0:
						if html_parent_el.text is None:
							html_parent_el.text = ""
						html_parent_el.text += text
					else:
						prev_el = html_parent_el[-1]
						if prev_el.tail is None:
							prev_el.tail = ""
						prev_el.tail += text

			# If we haven't dropped this tag in the previous code block and we
			# have not subsuming it into its parent, add it to its parent.
			elif html_el != html_parent_el:
				assert html_parent_el is not None
				html_parent_el.append(html_el)
				# Table columns and cells can be repeated
				for i in range(int(odt_el.attrib.get("table:number-columns-repeated", 1)) - 1):
					html_parent_el.append(deepcopy(html_el))

		return

	def convert_children(self, odt_el:ET._Element, html_el, list_style_name, depth):
		# Call the current function recursively to convert the ODT tag's children.
		for child in odt_el:
			self.convert_element(child, html_el, list_style_name, depth+1)

		# Now run through the children collapsing the unnecessary spans
		# which Google Docs creates for no apparent reason.
		prev_child = None
		for child in html_el:
			if prev_child is not None \
					and child.tag == "span" and prev_child.tag == "span" \
					and child.attrib == prev_child.attrib \
					and prev_child.text is not None \
					and (prev_child.tail is None or prev_child.tail == "") \
					and len(prev_child) == 0 and len(child) == 0:
				#print("collapsed")
				if child.text is not None:
					prev_child.text += child.text
				if child.tail is not None:
					prev_child.tail = child.tail
				html_el.remove(child)
			else:
				prev_child = child

		# Look for weird stuff with stress marks. We have seen ODT files with
		# tags between the character and the stress mark. Since the stress mark
		# is a combining character, this is an error. This may be a problem with
		# the handling of spans created to set the language.
		# We have to detect this problem since iPad browsers will not render
		# this erroneous sequence as the user intended.
		# We expect the user to fix the document by doing the following:
		# * open the document
		# * select the offending text with the stress mark
		# * note it says "Multiple Langauges" in status bar at the bottom of the window
		# * select the correct language
		# * save the document
		for child in html_el:
			if child.tag == "span":
				if child.text == "\u0301":
					raise OdfBadFormatting("Spurious stress mark span")
				if child.tail and child.tail.startswith("\u0301"):
					raise OdfBadFormatting("Combining stress mark between spans: %s" % child.text)

	def convert_index_mark(self, odt_el:ET._Element):
		"""Turn alphabetical index entry mark into a <span> with an ID"""
		assert odt_el.tag.startswith("text:alphabetical-index-mark")
		assert odt_el.text is None
		term = odt_el.attrib.get("text:string-value")
		if term is None:
			term = ""
			if odt_el.tail is not None:
				term += odt_el.tail
			el = odt_el.getnext()
			while el is not None and el.tag != "text:alphabetical-index-mark-end":
				term += element_extract_text(el)
				el = el.getnext()
		values = []
		for value in (odt_el.attrib.get("text:key1"), odt_el.attrib.get("text:key2"), term):
			if value is not None:
				values.append(value)
		html_el:ET._Element = E.span({
			"id":"idx%02d" % self.topic_index_counter,
			"data-index":json.dumps(values,separators=(",", ":")),
			})
		self.topic_index_counter += 1
		html_el.text = odt_el.tail
		odt_el.tail = None				# so it will not be copied to html_el.tail
		return html_el

	# This is broken out as a function because convert_element() was getting too long.
	# * If a frame contains an image, convert it to an <img>
	# * If the frame is anchored to the paragraph, convert it to a <div> and hoist it out.
	# * If the frame is anchored to a character, convert it to a <span> with
	#   display: inline-block. Convert the paragraphs into <span>s with display: block,
	#   since block level tags are not allowed inside <span>s.
	# In Libreoffice one may insert "Frames" and "Text Boxes" (which are listed as graphics
	# in the navigator). In the XML, text box is a special case of a frame. The only difference
	# we can discern in the XML is that its style lacks a style:parent-style-name attribute.
	# The value of the attribute seems to be immaterial. "Text Boxes" also have a
	# style:text-style-name attribute, but this removing it does not make them ordinary frames.
	#
	def convert_frame(self, odt_frame:ET._Element) -> ET._Element:
		assert odt_frame.tag == "draw:frame"
		if self.opts.debug:
			print(f"Frame: {repr(odt_frame.attrib)}")

		# If the frame is just a container for a single image,
		odt_images = odt_frame.xpath("./draw:image")
		if len(odt_images) > 0:
			if self.opts.debug:
				for i in range(len(odt_images)):
					print(f"  Image {i}: {odt_images[i].attrib}")
			html_el:ET._Element = E.img({
				"src": self.images.add(odt_images[0].attrib["xlink:href"]),
				})
			titles = odt_frame.xpath("./svg:title")
			if len(titles) > 0:
				html_el.attrib["alt"] = titles[0].text
			elif " " in (alt := odt_frame.attrib.get("draw:name","")):
				html_el.attrib["alt"] = alt
			else:
				print("  Warning: image without alt text")

		# If the frame is an actual frame,
		else:
			name = odt_frame.attrib["draw:name"]
			if name in self.opts.nav_names:
				html_el = E.nav()
				html_el.attrib["_hoistme"] = "true"
			elif odt_frame.attrib.get("text:anchor-type") == "as-char":		# <text:anchor-type
				html_el = E.span()
			else:		# "paragraph", "character"
				html_el = E.div()
				html_el.attrib["_hoistme"] = "true"
			html_el.attrib["id"] = name

		# Convert the frame's attributes into an inline CSS style
		style = []
		for odf_attrib, html_attrib, stop in (
				("style:rel-width", "width", True),
				("svg:width", "width", False),
				("svg:height", "height", False),
				#("min-width", "max-width"),		# FIXME: these four are not in ODF 1.3
				#("min-height", "min-height"),
				#("max-width", "max-width"),
				#("max-height", "max-height"),
				):
			if odf_attrib in odt_frame.attrib:
				style.append("%s:%s" % (html_attrib, odt_frame.attrib[odf_attrib]))
				if stop:
					break
		if "svg:x" in odt_frame.attrib:
			style.append("margin-left:%s" % odt_frame.attrib["svg:x"])
		html_el.attrib["style"] = ";".join(style)
		html_el.attrib["class"] = "frame"

		return html_el

	def frame_fixup(self, html_el:ET._Element) -> None:
		assert "frame" in html_el.attrib.get("class","").split()
		for el in html_el.iter():
			#print("Frame child:", el)
			if el.tag == "p":
				el.tag = "span"
				el.attrib["style"] = "display: block"

	def table_fixup(self, html_el:ET._Element, html_parent_el:ET._Element) -> ET._Element:
		"""Called once a table and all of its children have been converted"""
		assert html_el.tag == "table"

		# Create a <tbody> and move the <tr> elements into it.
		# We have to do this to pass XHTML 1.1 validation.
		tbody:ET._Element = E.tbody()
		for child in list(html_el):
			if child.tag == "tr":
				html_el.remove(child)
				tbody.append(child)
				for td in child:
					self.td_fixup(td)
		html_el.append(tbody)

		# Wrap the <table> in a <div> since this seems the only way we can
		# restrict its width on all browsers.
		restraint:ET._Element = E.div(html_el, {"class":"restrain"})

		# If "clear: both" is set in the table's style (which it will be for full-width tables),
		# copy it into the style of the wrapper. If the previous element is a heading, copy it into
		# the heading's style as well.
		if self.styles.claims[html_el].properties.get("clear","") == "both":
			restraint.attrib["style"] = "clear: both"
			if len(html_parent_el) >= 1:
				prev_el = html_parent_el[-1]
				if prev_el.tag in ("h1","h2","h3","h4","h5","h6"):
					prev_el.attrib["style"] = "clear: both"

		return restraint

	def td_fixup(self, td:ET._Element):
		assert td.tag == "td"

		# Table cells should not have text directly inside them (yet).
		assert td.text is None, "unexpected text: \"%s\"" % td.text

		# Nor should cells have trailing text.
		assert td.tail is None, "unexpected tail: \"%s\"" % td.tail

 		# If this <td> contains a single paragraph, subsume it.
		if len(td) == 1 and td[0].tag == "p":
			p = td[0]
			p_style = self.styles.claims[p]
			if not p_style.property_match("margin*") and not p_style.property_match("border"):
				classes = []
				if "class" in td.attrib:
					classes.append(td.attrib["class"])
				if "class" in p.attrib:
					classes.append(p.attrib["class"])
				if len(classes) > 0:
					td.attrib["class"] = " ".join(classes)
				if "lang" in p.attrib:
					td.attrib["lang"] = p.attrib["lang"]
				td.text = p.text
				for child in p:
					td.append(child)
				td.remove(p)
				if td.text is None or len(td.text) < 25:		# unwrap short <td>'s
					td.tail = ""
				# FIXME: Shouldn't this work even if there are multiple paragraphs in the <td>?
				if p_style.is_instance_of("Table_20_Heading"):
					td.tag = "th"
					style = self.styles.claims[td]
					assert isinstance(style, TableCellStyle)
					style.is_th = True

	#------------------------------------------------------------------
	# Pass 3
	#------------------------------------------------------------------

	def do_post_processing(self):

		# FIXME: Can we do this at the end of pass 2 instead of inserting it in the first place?
		# Hoist elements out of their parents where they have requested it.
		for el in self.html_body.xpath(".//*[@_hoistme='true']"):
			parent = el.getparent()
			grandparent = parent.getparent()
			grandparent.insert(grandparent.index(parent), el)
			if el.tail:
				if parent.text is None:		# FIXME: could there be a previous child which should get the text added to its tail?
					parent.text = ""
				parent.text += el.tail
				el.tail = None
			del el.attrib["_hoistme"]

		# Find the endnotes (currently <li> tags throughout the text) and move them to the end
		notes = list(self.html_body.xpath(".//li[@class='note']"))
		if len(notes) > 0:
			notes_ul:ET._Element = E.ul({"class":"notes"})
			for note in notes:
				note_citation = note.xpath("./div[@class='note-citation']")[0]

				# Create an <a> tag linked to the endnote
				a = deepcopy(note_citation)
				a.tag = "a"
				a.attrib["id"] = "lnk-" + note.attrib["id"]
				a.attrib["href"] = "#" + note.attrib["id"]

				# Replace the endnote with the <a> tag
				a.tail = note.tail
				note.tail = None
				parent = note.getparent()
				parent.insert(parent.index(note), a)

				# Move the text of the note-citation into an <a> tag
				backlink:ET._Element = E.a({
					"href": "#lnk-" + note.attrib["id"],
					})
				backlink.text = note_citation.text
				note_citation.text = None
				note_citation.append(backlink)

				# Move the endnote to the endnotes container
				notes_ul.append(note)
			self.html_body.append(notes_ul)

		for graphic in self.html_body.xpath(".//svg[@class='graphic']"):
			graphic.getparent().attrib["style"] = "position: relative;"
	#------------------------------------------------------------------
	# Resources Handling
	#------------------------------------------------------------------

	def add_script(self, script):
		"""Insert a Javascript into the head of the document"""
		script_tag:ET._Element = E.script({"type":"text/javascript"}, script)
		script_tag.tail = "\n"
		self.html_head.append(script_tag)

	def add_script_file(self, src:str):
		script:ET._Element = E.script({
			"type":"text/javascript",
			"src":src,
			"defer":"defer"
			})
		script.tail = "\n"
		self.html_head.append(script)

	def add_css(self, css):
		"""Insert CSS styles into the head of the document"""
		style_tag:ET._Element = E.style({"type": "text/css"})
		css = css.strip()
		css = re.sub(r"^\t\t\t", "", css, flags=re.MULTILINE)
		style_tag.text = "\n" + css + "\n"
		self.html_head.append(style_tag)

	def minimize_resources(self):
		"""Minify Javascript and CSS blocks in <head>"""
		for el in self.html_head.xpath("//script"):
			if el.attrib.get("type") == "text/javascript" and el.text is not None:
				el.text = jsmin(el.text)
		for el in self.html_head.xpath("//style"):
			if el.attrib.get("type") == "text/css" and el.text is not None:
				el.text = cssmin(el.text)

	#------------------------------------------------------------------
	# HTML Output
	#------------------------------------------------------------------

	def save_html(self, html_filename:str):
		"""Wrap <head> and <body> in <html> and write to disk"""
		with open(html_filename, "wb") as outfh:
			outfh.write(b"<!DOCTYPE HTML>\n")
			html:ET._Element = E.html(
				self.html_head,
				self.html_body,
				)
			if self.styles.default_language is not None:
				html.attrib["lang"] = self.styles.default_language
			ET.ElementTree(element=html).write(outfh, encoding="utf-8", pretty_print=True, method="html")
