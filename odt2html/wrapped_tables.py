import textwrap

# If a table's name contains the string "Box", convert it to to a box
# and its cells to child boxes which flow into it and wrap like words
# in a paragraph. To accomplish this this we:
# * Convert <table> to <div class="wrap">
# * Drop <col>, <tr>, and <tbody>
# * Convert the <td> elements to <div> elements and reinsert them
#
# FIXME: The way we fix up the styles is a horrible hack which breaks
# encapsulation. This was chosen as a low-risk temporary solution until
# style-handling can be overhauled.

class WrappedTables:
	def __init__(self, converter):
		self.debug = converter.opts.debug
		self.html_body = converter.html_body
		self.styles = converter.styles

	def run(self):
		if self.debug:
			print("  Fixing up wrappable tables...")
		count = 0
		for table in self.html_body.xpath(".//table[contains(@class, 'Wrap')]"):
			if self.debug:
				print("  Wrapping table \"%s\"" %  table.attrib["class"])

			# Convert table and its style to <div>
			table.tag = "div"
			table_style = self.styles.claims[table]
			table_style.template = "DIV.%s"
			# TODO: Convert to new style system
			#if "max-width" in table_style.properties:
			#	del table_style.properties["max-width"]

			boxes = []
			for tchild in table:
				if tchild.tag == "tbody":
					for tr in tchild:
						style = self.styles.claims.get(tr)
						if style is not None:
							style.template = "DIV.%s > DIV"
							style.name = table_style.name

						for td in tr:
							td.tag = "div"
							style = self.styles.claims.get(td)
							if style is not None and style.template != "DIV.%s":
								style.template = "DIV.%s"
								# TODO: Translate to new style system
								#vertical_align = style.properties.pop("vertical-align",None)
								#style.properties["justify-content"] = {
								#	"top":"flex-start",
								#	"middle":"center",
								#	"bottom":"flex-end",
								#	}.get(vertical_align,"center")
							boxes.append(td)

				elif tchild.tag == "col":
					style = self.styles.claims.get(tchild)
					if style is not None:		# deepcopy()ed lack style claim
						style.template = "DIV.%s > DIV"
						style.name = table_style.name

				table.remove(tchild)

			for box in boxes:
				table.append(box)

			table.attrib["class"] += " wrap"

			# Since this is no longer real time, get rid of the size-limiting wrapper
			restraint = table.getparent()
			grandparent = restraint.getparent()
			grandparent.replace(restraint, table)

			count += 1

		if count > 0:
			self.styles.plugin_rules.append(textwrap.dedent("""\
				DIV.wrap { display: flex; flex-flow: row wrap }
				DIV.wrap DIV { display: inline-block; margin: 1px; display: flex; flex-direction: column }
				"""))
