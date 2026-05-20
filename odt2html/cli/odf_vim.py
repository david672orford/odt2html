"""Edit the XML files with in an ODF file in Vim"""

import argparse
import os
import subprocess

from odt2html.odf_tool import OdfTool

def main() -> int:
	parser = argparse.ArgumentParser(
		description = __doc__,
		formatter_class = argparse.RawDescriptionHelpFormatter,
		argument_default = argparse.SUPPRESS,
		)
	_=parser.add_argument("--styles", dest="subfilename", action="store_const", const="styles.xml", help="Edit styles.xml")
	_=parser.add_argument("--meta", dest="subfilename", action="store_const", const="meta.xml", help="Edit meta.xml")
	_=parser.add_argument("--settings", dest="subfilename", action="store_const", const="settings.xml", help="Edit settings.xml")
	_=parser.add_argument("--content", dest="subfilename", action="store_const", const="content.xml", help="Edit content.xml")
	_=parser.add_argument("filename", help="Odf file to open")
	_=parser.set_defaults(subfilename="content.xml")
	opts = parser.parse_args()

	odt = OdfTool(opts.filename)
	tmp_for_vim = "%s-edit.xml" % opts.filename

	# Write that part to a temporary file pretty printed.
	with open(tmp_for_vim, "w", encoding="utf-8") as tf:
		tf.write(odt.get_pretty_text(opts.subfilename))

	# Run Vim.
	saved_mtime = os.path.getmtime(tmp_for_vim)
	subprocess.check_call(("vim", tmp_for_vim))
	if os.path.getmtime(tmp_for_vim) == saved_mtime:
		print("No changes.")
	else:
		print("Applying changes...")
		odt.set_pretty_text(opts.subfilename, tmp_for_vim)
		odt.save()
		print("Done.")

	os.unlink(tmp_for_vim)
	return 0
