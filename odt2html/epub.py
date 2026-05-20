import zipfile
import textwrap
import uuid

import lxml.etree as ET
from lxml.builder import E

# Create an EPUB file. An EPUB file is a zip file containing:
# * The document as one or more XHTML files
# * Images
# * An XML table of contents
# * A few other metadata files
class EpubWriter:
	def __init__(self, converter):
		self.opts = converter.opts
		self.metadata = converter.metadata
		self.html_head = converter.html_head
		self.html_body = converter.html_body
		self.images = converter.images
		self.styles = converter.styles
		self.h1s = converter.h1s

	def save(self, epub_filename:str):
		epub = zipfile.ZipFile(epub_filename, "w")
		epub_uuid = uuid.uuid4().urn

		# MIME type must be first in file and uncompressed
		epub.writestr("mimetype", "application/epub+zip", zipfile.ZIP_STORED)

		# Boilerplate file
		epub.writestr("META-INF/container.xml", textwrap.dedent("""\
			<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
				<rootfiles>
					<rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
				</rootfiles>
			</container>
			"""), zipfile.ZIP_DEFLATED)

		# One copy of stylesheet
		epub.writestr("stylesheet.css", self.epub_css().encode("utf-8"), zipfile.ZIP_DEFLATED)

		#---------------------------------------------
		# Start building Content Index
		# content.opf
		#---------------------------------------------
		index_tpl = ET.Element(
			"{http://www.idpf.org/2007/opf}package",
			{	"version": "2.0",
				"unique-identifier": "bookid",
				},
			nsmap = {
				None:"http://www.idpf.org/2007/opf",
				"dc":"http://purl.org/dc/elements/1.1/"
				},
			)

		# Metadata about the book
		metadata:ET._Element = E.metadata()
		index_tpl.append(metadata)
		metadata.append(E("{http://purl.org/dc/elements/1.1/}title",self.metadata["title"]))
		metadata.append(E("{http://purl.org/dc/elements/1.1/}identifier",epub_uuid,{"id":"bookid"}))
		metadata.append(E("{http://purl.org/dc/elements/1.1/}language","en-US"))

		# List of files in the book
		manifest:ET._Element = E.manifest()
		index_tpl.append(manifest)

		# Style for rendering pages in the book
		manifest.append(E.item({
			"id":"css",
			"href":"stylesheet.css",
			"media-type":"text/css",
			}))

		# File which gives the book structure
		manifest.append(E.item({
			"id":"ncx",
			"href":"toc.ncx",
			"media-type":"application/x-dtbncx+xml",
			}))

		spine:ET._Element = E.spine({"toc":"ncx"})
		index_tpl.append(spine)

		# FIXME: No <guide> section. Do we need one?

		#-------------------------------------------------------------
		# Add the HTML, possibly split into a separate file for
		# each <section> in the ODT file.
		#-------------------------------------------------------------

		self.html_head.append(E.link({
			"type":"text/css",
			"rel":"stylesheet",
			"href":"stylesheet.css",
			}))

		remaining = list(self.html_body)
		i = 0
		while len(remaining) > 0:
			if self.opts.split_by_sections:
				chunk:ET._Element = E.body()
				chunk.append(remaining.pop(0))
				while len(remaining) > 0 and not (remaining[0].tag == "div" and remaining[0].attrib.get("id","").startswith("topsect")):
					chunk.append(remaining.pop(0))
			else:
				chunk = self.html_body
				remaining = []

			content_id = "content%d" % i
			content_filename = "content%d.html" % i

			# Add this part to <manifest> element of content.opf so
			# that the ereader will know it is part of the ebook.
			manifest.append(E.item({
				"id":content_id,
				"href":content_filename,
				"media-type":"application/xhtml+xml",
				}))

			# Add this part to <spine> element of content.opf so the
			# ereader will know where it comes in the reading order.
			spine.append(E.itemref({
				"idref":content_id
				}))

			# Generate the HTML
			html:ET._Element = E.html(self.html_head, chunk)
			html.attrib["xmlns"] = "http://www.w3.org/1999/xhtml"
			html_elementtree = ET.ElementTree(element=html)
			text = '<?xml version="1.0" encoding="UTF-8"?>\n' \
				+ '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n' \
				+ ET.tostring(html_elementtree, encoding="utf-8", pretty_print=True)

			# Add the HTML to the EPUB file
			epub.writestr(content_filename, text, zipfile.ZIP_DEFLATED)

			i += 1

		#---------------------------------------------
		# Zip each embedded image and add it to
		# the manifest
		#---------------------------------------------
		i = 1
		for image in self.images:
			i += 1
			manifest.append(E.item({
				"id":"img-%d" % i,
				"href":image.filename,
				"media-type":image.mimetype,
				}))

			epub.writestr(image.filename, image.get_data(), image.compression)

		#---------------------------------------------
		# Zip content index and table of contents
		#---------------------------------------------
		epub.writestr("content.opf",
			ET.tostring(ET.ElementTree(element=index_tpl), encoding="utf-8", pretty_print=True),
			zipfile.ZIP_DEFLATED
			)
		epub.writestr("toc.ncx", self.epub_toc(epub_uuid), zipfile.ZIP_DEFLATED)

	# Generate style for an EPUB file
	def epub_css(self):
		# The base CSS stylesheet for ebook readers. Remember that
		# this is CSS 2.1, so no @media queries.
		css = textwrap.dedent("""\
			HTML, BODY, H1, H2, H3, H4, H4, P, UL, LI { margin: 0; padding: 0 }
			BODY { margin: 0.125in; font-size: 12pt }
			H1, H2, H3, H4, H4 { font-size: inherit }
			UL, OL { list-style-position: outside }
			TABLE { border-collapse: collapse }
			TH, TD { vertical-align: top }
			HR.pagebreak { margin: 0.5in -0.5in 0.5in -0.5in }
			SPAN.space { white-space: pre-wrap }
			""")

		# Add the converted styles from the ODT file, again limited to CSS 2.1.
		css += self.styles.get_css(2.1)

		return css

	# Generate the Navigation Control file for XML (NCX) for an EPUB file.
	# This is the machine-readable table of contents which the ereader
	# may incorporate into its navigation controls.
	def epub_toc(self, epub_uuid):
		ncx = ET.Element(
			"{http://www.daisy.org/z3986/2005/ncx/}ncx",
			{	"version": "2005-1",
				},
			nsmap = {
				None:"http://www.daisy.org/z3986/2005/ncx/",
				},
			)

		ncx_head:ET._Element = E.head()
		ncx.append(ncx_head)
		ncx_head.append(E.meta({"name":"dtb:uid","content":epub_uuid}))
		ncx_head.append(E.meta({"name":"dtb:depth","content":"1"}))
		ncx_head.append(E.meta({"name":"dtb:totalPageCount","content":"0"}))
		ncx_head.append(E.meta({"name":"dtb:maxPageNumber","content":"0"}))

		ncx.append(E.docTitle(E.text(self.metadata["title"])))

		ncx_navmap:ET._Element = E.navMap()
		ncx.append(ncx_navmap)

		i = 1
		for h_filename, h_id, h_text in self.h1s:
			print("  H1:", h_filename, h_id, h_text)
			ncx_navmap.append(
				E.navPoint(
					E.navLabel(E.text(h_text)),
					E.content({"src":"%s#%s" % (h_filename, h_id)}),
					{	"id":"navpoint-%d" % i,
						"playOrder":"%d" % i
						},
					),
				)
			i += 1

		text = '<?xml version="1.0" encoding="UTF-8"?>\n' \
			+ '<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">\n' \
			+ ET.tostring(ET.ElementTree(element=ncx), encoding="utf-8", pretty_print=True)

		return text
