"""
These two classes are used to load an index.html which contains links to the
HTML versions which odt2html will produce. These are used to create backlinks
in the converted documents. We also draw metadata from these index.html pages.
"""

import re
import json
import os
from urllib.parse import unquote

import lxml.html

class Odt2HtmlDirectoryIndexes(list):
	def find_entry(self, search_filename:str):
		# Search the indexes specified with --docindex= options looking for
		# a link to the specified document
		for docindex in self:
			#print(" docindex.dirname:", docindex.dirname)
			#print(" search_filename:", search_filename)
			if docindex.dirname != "":
				if search_filename.startswith(docindex.dirname):
					search_filename = search_filename[len(docindex.dirname):]
				else:		# FIXME: this is a hack
					search_filename = "../" + search_filename
			if search_filename in docindex:
				return docindex[search_filename]
		return None

class Odt2HtmlDirectoryIndex(dict):
	def __init__(self, filename:str):
		self.filename:str = filename	# HTML file from which this docindex was loaded
		self.site_name = None			# FIXME: loaded, but unused
		self.site_url = None			# FIXME: loaded, but unused
		self.publisher = None
		self.author = None
		self.breadcrumblist = []

		# Listed files will be relative to this.
		if "/" in filename:
			self.dirname:str = os.path.dirname(filename) + "/"
		else:
			self.dirname = ""

		with open(filename) as fh:
			docindex = lxml.html.parse(fh)

		# Collect information about the docindex entry for each listed document.
		for section in docindex.xpath("//section"):
			section_id = section.attrib.get("id")
			h2s = section.xpath("./h2")

			if len(h2s) == 1:
				section_heading = re.sub(r"\s+\(.+\)\s*$", "", h2s[0].text)		# parenthetical removed
			else:
				section_heading = None

			for anchor in section.xpath(".//a"):
				href = anchor.attrib.get("href")
				if href:
					filename = unquote(href)
					self[filename] = Odt2HtmlArticle(self, section_id, section_heading, anchor.text_content().strip())

		# Collect site metadata from the docindex itself.
		for script in docindex.xpath("//script[@type='application/ld+json']"):
			data = json.loads(script.text)
			for item in data if type(data) is list else (data,):

				# Save author and publisher so that we can copy it into the Article metadata.
				if item["@type"] == "Organization":
					self.publisher = {
						"@type":item["@type"],
						"name":item["name"],
						"logo":item["logo"]
						}
					self.author = {
						"@type":item["@type"],
						"name":item["name"],
						}
					continue

				# FIXME: This is currently unused. Can it replace --site-url= and --site-name=?
				if item["@type"] == "WebSite":
					self.site_name = item["name"]
					self.site_url = item["url"]
					if not self.site_url.endswith("/"):
						self.site_url += "/"
					continue

				# Unless an docindex page is the top page of the site it should have breadcrumbs
				# to show where it is in the site. Save them so that we can propagate them
				# to the docindexed document.
				if item["@type"] == "BreadcrumbList":
					self.breadcrumblist = item["itemListElement"]

		if self.site_name is None and len(self.breadcrumblist) == 0:
			print("Warning: docindex \"%s\" lacks Schema.org metadata" % self.filename)

	def __str__(self):
		return "<Odt2Htmldocindex filename=\"%s\", %d entries>" % (self.filename, len(self.keys()))

class Odt2HtmlArticle:
	def __init__(self, dirindex:Odt2HtmlDirectoryIndex, section_id, section_heading, linked_text:str):
		self.dirindex:Odt2HtmlDirectoryIndex = dirindex
		self.section_id = section_id			# <section id="X">
		self.section_heading = section_heading	# <section><h2> text
		if u"—" in linked_text and section_id is not None:
			self.title:str = linked_text.split(u"—",1)[1]
		else:
			self.title = linked_text
	def __str__(self):
		return "<Odt2HtmldocindexArticle title=\"%s\">" % self.title
