import os
import json
from urllib.parse import quote

from PIL import Image
import lxml.etree as ET
from lxml.builder import E

class HtmlMetadata:
	def __init__(self, converter):
		self.site_name = converter.opts.site_name
		self.site_url = converter.opts.site_url
		self.page_url = converter.opts.site_url + quote(converter.output_filename)
		self.dirindexes = converter.opts.dirindexes
		self.dirindex_entry = converter.dirindex_entry
		self.metadata = converter.metadata
		self.html_head = converter.html_head

	def run(self):
		if "description" in self.metadata:
			self.html_head.append(E.meta({
				"name":"description",
				"content":self.metadata["description"],
				}))
		self.add_opengraph_metadata()
		self.add_schema_org_metadata()

	def add_opengraph_metadata(self):
		"""Add Open Graph tags for social networking"""
		# http://ogp.me/
		# https://css-tricks.com/essential-meta-tags-social-media/
		# https://cards-dev.twitter.com/validator
		# https://developers.facebook.com/tools/debug/
		if "og:image" in self.metadata:
			assert self.metadata["og:image"].endswith(".png")
			assert os.path.isfile(self.metadata["og:image"])
			assert "title" in self.metadata
			if self.site_name is not None:
				self.html_head.append(E.meta({"property":"og:site_name","content":self.site_name}))
			self.html_head.append(E.meta({"property":"og:type","content":"article"}))
			self.html_head.append(E.meta({"property":"og:title","content":self.metadata["title"]}))
			if "description" in self.metadata:
				self.html_head.xpath('./meta[@name="description"]')[0].attrib["property"] = "og:description"
			self.html_head.append(E.meta({"property":"og:url","content":self.page_url}))
			self.html_head.append(E.meta({"property":"og:image","content":self.site_url + quote(self.metadata["og:image"])}))
			with Image.open(self.metadata["og:image"]) as img:
				width, height = img.size
			self.html_head.append(E.meta({"property":"og:image:width","content":str(width)}))
			self.html_head.append(E.meta({"property":"og:image:height","content":str(height)}))
			if "og:image:alt" in self.metadata:
				self.html_head.append(E.meta({"property":"og:image:alt","content":self.metadata["og:image:alt"]}))
			self.html_head.append(E.meta({"name":"twitter:card","content":"summary_large_image"}))

	def add_schema_org_metadata(self):
		"""
		Added Schema.org metadata to the <head> of the generated HTML document
		See: https://developers.google.com/search/docs/data-types/article
		"""
		linked_data = []

		if "og:image" in self.metadata:
			assert len(self.dirindexes) > 0
			index = self.dirindexes[0]
			assert self.metadata["og:image"].endswith(".png")
			assert os.path.isfile(self.metadata["og:image"])
			assert "title" in self.metadata
			assert "Publication date" in self.metadata
			assert index.publisher
			assert index.author
			article = {
				"@context": "http://schema.org",
				"@type": "Article",
				"headline": self.metadata["title"],
				"mainEntityOfPage": self.page_url,
				"image": [
					self.site_url + quote(self.metadata["og:image"])
					],
				"publisher": index.publisher,
				"author": index.author,
				"datePublished": self.metadata["Publication date"],
				"dateModified": self.metadata["Revision date"]
				}
			if "description" in self.metadata:
				article["description"] = self.metadata["description"]
			linked_data.append(article)

		if self.dirindex_entry is None:
			print("  Warning: document not listed in index, no BreadcrumbList created")
		else:
			breadcrumblist = self.dirindex_entry.dirindex.breadcrumblist[:]

			# the index section which lists this document (if there is one)
			if self.dirindex_entry.section_id is not None and self.dirindex_entry.section_heading is not None:
				breadcrumblist.append(
					{
					"@type": "ListItem",
					"position": len(breadcrumblist) + 1,
					"item": {
						"@id": self.site_url + "#" + self.dirindex_entry.section_id,
						"name": self.dirindex_entry.section_heading
						}
					})

			# this document itself
			breadcrumblist.append({
				"@type": "ListItem",
				"position": len(breadcrumblist) + 1,
				"item": {
					"@id": self.page_url,
					"name": self.dirindex_entry.title
					}
				})

			linked_data.append({
				"@context": "http://schema.org",
				"@type": "BreadcrumbList",
				"itemListElement": breadcrumblist,
				})

		if len(linked_data) > 0:
			script:ET._Element = E.script({"type":"application/ld+json"})
			script.text = "\n" + json.dumps(linked_data, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
			script.tail = "\n"
			self.html_head.append(script)
