import re

class Linter:
	def __init__(self, converter):
		self.html_body = converter.html_body

	def warnings_formatting(self):
		"""Print list of instances of direct formatting"""
		for el in self.html_body.xpath(".//*"):
			if el.tag not in ("p", "span"):
				continue
			classes:str = el.attrib.get("class","")
			if re.match(r"^[PT]\d+$", classes):
				while True:
					parent = el.getparent()
					if parent.tag == "span":
						el = parent
					else:
						break
				text = el.xpath("string()")
				if el.tail:
					text += el.tail
				for el2 in el.xpath("following-sibling::*"):
					if len(text) >= 50:
						break
					text += el2.xpath("string()")
					if el2.tail:
						text += el2.tail
				text = text[:50]
				print("  Direct formatting:", el.tag, classes, text)
