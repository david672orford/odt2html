"""Load a template HTML file and copy parts to the output tree"""

import os

import lxml.html

class HtmlTemplate:
	def __init__(self, converter):
		self.debug = converter.opts.debug
		self.template = converter.opts.template
		self.metadata = converter.metadata
		self.html_head = converter.html_head
		self.title_el = converter.title_el
		self.html_body = converter.html_body
		self.odt_filename = converter.odt_filename
		self.output_dirname = converter.output_dirname
		self.docdir_entry = converter.docdir_entry

	def run(self):
		template = lxml.html.parse(open(self.template))

		# Copy <link>, <style>, and <script> elements from the <head> of the
		# template to the <head> of the document.
		for el in template.xpath("//head")[0]:
			if el.tag in ("link", "style", "script"):
				self.html_head.append(el)

		# If the template has a <title>, prepend it to the document's title
		template_title = template.xpath("//head/title")
		if template_title is not None:
			template_title = template_title[0].text
			if template_title:
				self.title_el.text = "%s: %s" % (template_title, self.metadata["title"])

		# Create value to interpolate below as BACK_TO_INDEX
		#
		# FIXME: this probably contains lots of assumptions about the directory
		# from which odt2html was invoked. This probably also does not work
		# with more than one level of index since we do not walk to the root of
		# the index tree.
		if self.output_dirname == ".":
			levels = 0
		else:
			levels = (self.output_dirname.count("/") + 1)
			if self.docdir_entry is not None and self.docdir_entry.index.dirname != "":
				levels -= self.docdir_entry.index.dirname.count("/")
		back_to_index = ("../" * levels) if levels > 0 else "./"

		# If available, add the fragment identifier of the index section which lists this document
		if self.docdir_entry is not None and self.docdir_entry.section_id is not None:
			back_to_index = "%s#%s" % (back_to_index, self.docdir_entry.section_id)

		# Copy elements from the template's body while interpolating
		# various values indicated in {{varname}} notation.
		basename = os.path.splitext(os.path.basename(self.odt_filename))[0]
		i = 0
		for template_header in template.xpath("//body/*"):
			for el in ((template_header,) + tuple(template_header.xpath(".//*"))):
				if el.text:
					el.text = el.text.replace("{{TITLE}}", self.metadata["title"])
				if el.tail:
					el.tail = el.tail.replace("{{TITLE}}", self.metadata["title"])
				if "href" in el.attrib:
					if el.attrib["href"] == "{{ODT}}":
						el.attrib["href"] = "%s.odt" % basename
					elif el.attrib["href"] == "{{PDF}}":
						el.attrib["href"] = "%s.pdf" % basename
					elif "{{BACK_TO_DOCDIR}}" in el.attrib["href"]:
						el.attrib["href"] = el.attrib["href"].replace("{{BACK_TO_DOCDIR}}", back_to_index)

			self.html_body.insert(i, template_header)
			i += 1
