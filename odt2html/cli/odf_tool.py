#! /usr/bin/python3

import sys
import os
import re
import datetime
import argparse

import lxml.etree as ET

from odt2html.odf_tool import OdfTool, namespaces, Styles

def valid_string(value:str) -> str:
	if len(value) == 0:
		raise argparse.ArgumentTypeError("Empty value disallowed")
	return value

def valid_regexp(value:str) -> re.Pattern:
	value = valid_string(value)
	try:
		pattern = re.compile(value)
	except re.error as e:
		raise argparse.ArgumentTypeError("Not a valid regular expression: %s" % str(e))
	return pattern

def cmd_show_metadata(args:list[str]) -> int:
	"""show-metadata <filename>\tPrint the document's metadata"""
	for filename in args:
		print("%s" % filename)
		odt = OdfTool(filename)
		for item in odt.get_metadata():
			if item.tag.endswith("}user-defined"):
				print("  %s: %s" % (item.attrib["{%s}name" % namespaces["meta"]], item.text))
			elif item.text is not None:
				print("  %s: %s" % (ET.QName(item).localname, item.text))
			else:
				print("  %s:" % ET.QName(item).localname)
				for name, value in item.attrib.items():
					print("    %s: %s" % (ET.QName(name).localname, value))
		exit 0

def cmd_show_used_styles(args:list[str]) -> int:
	"""show-used-styles <filename>\tShow which document styles are actually used"""
	for filename in args:
		print("%s" % filename)
		odt = OdfTool(filename)
		styles = Styles(odt)
		used_styles = []
		for style in styles.values():
			if style.group_name == "styles.xml" and style.used_directly:
				used_styles.append(style.name.replace("_20_"," ").replace("_5f_","_"))
		for used_style in sorted(used_styles):
			print("  %s" % used_style)
	return 0

def cmd_strip(args:list[str]) -> int:
	"""strip [--unused-styles] <filename>\tRemove cruft"""
	opt_unused_styles = False
	for filename in args:
		if filename == "--unused-styles":
			opt_unused_styles = True
			continue
		print(filename)
		odt = OdfTool(filename)
		changes = 0
		changes += odt.set_default_language("en", "US")
		changes += odt.strip_en()
		changes += odt.strip_rsid()
		changes += odt.strip_asian_fonts()
		changes += odt.strip_configurations()
		changes += odt.strip_thumbnails()
		if opt_unused_styles:
			changes += strip_unused_styles(odt)
		print("  %d change(s)" % changes)
		if changes > 0:
			odt.save()
	return 0

def cmd_strip_unused_styles(args:list[str]) -> int:
	"""strip-unused-styles <filename>\tRemove document styles which are not actually used"""
	for filename in args:
		print("%s" % filename)
		odt = OdfTool(filename)
		changes = strip_unused_styles(odt)
		if changes > 0:
			odt.save()
	return 0

def strip_unused_styles(odt:OdfTool) -> int:
	"""Remove unused styles"""
	styles = Styles(odt)
	strippable_styles = set(["style", "list-style", "master-page"])

	changes = 0
	for style in styles.values():
		if not style.used:
			if style.tag not in strippable_styles:
				print("  Deletion not implemented: %s" % str(style))
			else:
				assert style.name is not None
				print("  Deleting: %s" % str(style))
				style.delete()
				changes += 1

	print("  Removing %d style(s)" % changes)
	return changes

def cmd_strip_revisions(args:list[str]) -> int:
	"""strip-revisions <filename>\tRemove information about document revisions"""
	for filename in args:
		odt = OdfTool(filename)
		changes = odt.strip_rsid()
		print("%s %d change(s)" % (filename, changes))
		if changes > 0:
			odt.save()
	return 0

def cmd_strip_thumbnails(args:list[str]) -> int:
	"""strip-thumbnails <filename>\tRemove document thumbnails"""
	for filename in args:
		odt = OdfTool(filename)
		changes = odt.strip_thumbnails()
		if changes > 0:
			odt.save()
	return 0

def cmd_set_date(args:list[str]) -> int:
	"""set-date <regexp> <string> <filename>\tUpdate user-defined "Copyright" and "Revision date"."""
	parser = argparse.ArgumentParser()
	_=parser.add_argument("copyright-check", type=valid_regexp)
	_=parser.add_argument("copyright-template", type=valid_string)
	_=parser.add_argument("filenames", nargs="+", help="List of files to process")
	opts = parser.parse_args(args)
	for filename in opts.filenames:
		print("%s" % filename)
		copyright_check_re = re.compile(opts.copyright_check, re.IGNORECASE)
		today = datetime.date.today()
		new_revision_date = today.isoformat()
		new_copyright = opts.copyright_template % today.year
		odt = OdfTool(filename)
		changes = 0
		current_copyright = odt.get_user_metadata("Copyright")
		if current_copyright is not None and copyright_check_re.search(current_copyright) and current_copyright != new_copyright:
			changes += odt.set_user_metadata("Copyright", new_copyright)
		current_revision_date = odt.get_user_metadata("Revision date")
		if current_revision_date != new_revision_date:
			changes += odt.set_user_metadata("Revision date", new_revision_date)
		print("  %d change(s)" % changes)
		if changes > 0:
			odt.save()
	return 0

def cmd_set_template(args:list[str]) -> int:
	"""set-template <template> <filename>\tChange the document's template"""
	template_filename = args[0]
	template_title = os.path.splitext(os.path.basename(template_filename))[0]
	print("Template filename:", template_filename)
	print("Template title:", template_title)
	assert os.path.exists(template_filename)
	for filename in args[1:]:
		print("ODF filename:", filename)
		template_href = os.path.join(
			"..",	# represents the ODF file
			os.path.relpath(template_filename, filename)
			)
		print("Template href:", template_href)
		odt = OdfTool(filename)
		changes = 0
		meta = odt.get_metadata()
		templates = meta.xpath("./meta:template", namespaces=namespaces)
		if len(templates) == 0:
			el = ET.Element("{%s}template" % namespaces["meta"])
			el.attrib["{%s}type" % namespaces["xlink"]] = "simple"
			el.attrib["{%s}actuate" % namespaces["xlink"]] = "onRequest"
			el.attrib["{%s}title" % namespaces["xlink"]] = template_title
			el.attrib["{%s}href" % namespaces["xlink"]] = template_href
			meta.append(el)
			changes += 1
		elif len(templates) == 1:
			if templates[0].attrib["{%s}title" % namespaces["xref"]] != template_title:
				templates[0].attrib["{%s}title" % namespaces["xref"]] = template_title
				changes += 1
			if templates[0].attrib["{%s}href" % namespaces["xref"]] != template_href:
				templates[0].attrib["{%s}href" % namespaces["xref"]] = template_href
				changes += 1
			if "{%s}date" % namespaces["meta"] in templates[0].attrib:
				del templates[0].attrib["{%s}date" % namespaces["meta"]]
				changes += 1
		else:
			raise AssertionError("multiple templates not expected")
		print("  %d change(s)" % changes)
		if changes > 0:
			odt.save()
	return 0

def cmd_set_default_language(args:list[str]) -> int:
	"""set-default-language <filename.odt>\tSet the default language to English"""
	for filename in args:
		print("%s" % filename)
		odt = OdfTool(filename)
		changes = odt.set_default_language("en", "US")
		#changes += odt.strip_en()
		print("  %d change(s)" % changes)
		if changes > 0:
			odt.save()
	return 0

def cmd_replace_emdash(args:list[str]) -> int:
	"""replace-emdash <filename.odt>\tReplace '--' with '—' through document"""
	for filename in args:
		print(filename)
		odt = OdfTool(filename)
		changes = odt.replace("--", u"—")
		print("  %d change(s)" % changes)
		if changes > 0:
			odt.save()
	return 0

#=============================================================================
# Main
#=============================================================================

def main():
	cmd_functions = list(filter(lambda item: item.startswith("cmd_"), globals().keys()))
	if len(sys.argv) < 2:
		sys.stderr.write("Usage: ootool <subcommand>\n")
		sys.stderr.write("Subcommands:\n")
		for cmd_function in cmd_functions:
			doc = globals()[cmd_function].__doc__
			summary, description = doc.split("\t")
			assert "cmd_" + summary.split()[0].replace("-","_") == cmd_function
			print(" %-37s %sn" % (summary, description))
		return 1	

	sys.argv.pop(0)
	subcommand = sys.argv.pop(0)
	cmd_function = subcommand.replace("-","_")

	if cmd_function not in cmd_functions:
		print("%s: Unrecognized subcommand" % subcommand, file=sys.stderr)
		print("Use \"%s help\" to get help.\n" % subcommand, file=sys.stderr)
		return 1

	return globals()[cmd_function](sys.argv))

