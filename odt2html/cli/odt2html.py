"""Convert files in Opendocument Text (ODT) format to Hypertext Markup Language (HTML)"""

import sys
import os
import argparse

from odt2html.console import Console
from odt2html.converter import Odt2Html
from odt2html.exceptions import OdfException
from odt2html.config import Odt2HtmlConfig
from odt2html.dirindexes import Odt2HtmlDirectoryIndex

class Opts(Odt2HtmlConfig):
	"""Add addition options used by the CLI interface and file processing loop"""
	verbose:bool = False
	force:bool = False
	filenames:list[str] = []
	outdir:str | None = None

def valid_string(value:str) -> str:
	if len(value) == 0:
		raise argparse.ArgumentTypeError("Empty value disallowed")
	return value

def valid_url(value:str) -> str:
	value = valid_string(value)
	if not value.endswith("/"):
		value += "/"
	return value

def valid_list(value:str) -> list[str]:
	return value.split(",")

def valid_file(value:str) -> str:
	value = valid_string(value)
	if not os.path.isfile(value):
		raise argparse.ArgumentTypeError(f"File not found: {value}")
	return value

def valid_dir(value:str) -> str:
	value = valid_string(value)
	if not os.path.isdir(value):
		raise argparse.ArgumentTypeError(f"Directory not found: {value}")
	return value

def valid_dirindex(value:str) -> Odt2HtmlDirectoryIndex:
	value = valid_file(value)
	return Odt2HtmlDirectoryIndex(value)

def main() -> int:
	parser = argparse.ArgumentParser(
		description = __doc__,
		formatter_class = argparse.RawDescriptionHelpFormatter,
		argument_default = argparse.SUPPRESS,
		)
	_=parser.add_argument("--debug", action="store_true", help="Print details of the conversion process")
	_=parser.add_argument("--verbose", action="store_true", help="List files processed and whether they are rebuilt")
	_=parser.add_argument("--force", action="store_true", help="Rebuild even if source file is unmodified")
	_=parser.add_argument("-o", "--outdir", type=valid_string, help="Write HTML files to this directory, rather than dirctory of each ODT file")
	_=parser.add_argument("--epub", dest="output_format", action="store_const", const="epub", help="Create Epub containing one HTML file per section")
	_=parser.add_argument("--warnings-formatting", action="store_true", help="List instances of direct formatting")
	_=parser.add_argument("--font-support-level", type=int, choices=(0,1,2), help="0=weight and slant, 1=generic families, 2=specified families")
	_=parser.add_argument("--dirindex", dest="dirindexes", action="append", type=valid_dirindex, metavar="HTML_FILE", help="index.html listing these documents")
	_=parser.add_argument("--index", dest="dirindexes", action="append", type=valid_dirindex, help=argparse.SUPPRESS)
	_=parser.add_argument("--template", type=valid_file, help="HTML file with <head> and <body> boilerplate to add")
	_=parser.add_argument("--site-name", type=valid_string, help="Name of website for Opengraph metadata")
	_=parser.add_argument("--site-url", type=valid_url, help="Base URL of site for constructing page URLs")
	_=parser.add_argument("--nav-names", type=valid_list, metavar="LIST", help="Names frames to convert as <nav> elements")
	_=parser.add_argument("--player-lib-dir", type=valid_dir, metavar="PATH", help="Path on web server to media player files, relative to HTML")
	_=parser.add_argument("filenames", nargs="+", help="List of files to process")
	opts = parser.parse_args(namespace=Opts())

	console = Console()

	count_total = 0
	count_built = 0
	count_rebuilt = 0
	for filename in opts.filenames:
		if opts.verbose:
			console.banner(filename, color="blue")

		if not os.path.exists(filename):
			sys.stderr.write(f"File does not exist: {filename}\n")
			return 1

		filename_mtime = os.path.getmtime(filename)

		basename, ext = os.path.splitext(filename)
		if ext != ".odt":
			sys.stderr.write(f"Not an ODT file: {filename}\n")
			return 1
		if opts.outdir is None:
			output_filename = "%s.%s" % (basename, opts.output_format)
		else:
			output_filename = os.path.join(opts.outdir, "%s.%s" % (os.path.basename(basename), opts.output_format))

		count_total += 1
		build = False
		if not os.path.exists(output_filename):
			if opts.verbose:
				print("  Building...")
			count_built += 1
			build = True
		elif opts.debug or opts.force or os.path.getmtime(output_filename) < filename_mtime:
			if opts.verbose:
				print("  Rebuilding...")
			count_rebuilt += 1
			build = True

		if build:
			if os.path.exists(output_filename):
				os.unlink(output_filename)

			gz_filename = "%s.gz" % output_filename
			if os.path.exists(gz_filename):
				os.unlink(gz_filename)

			# Perform the conversion
			try:
				_=Odt2Html(filename, output_filename, opts, console)
			except OdfException as e:
				console.message("Conversion failed: ", f"{e.__doc__}: {str(e)}", color="red", file=sys.stderr)
				if not opts.debug:
					print("Rerun with --debug for a stack trace.", file=sys.stderr)
				return 1

			# Make the creation time of the HTML file one millisecond after the
			# creation time of the ODT file from which it was made.
			os.utime(output_filename, (filename_mtime + 0.01, filename_mtime + 0.01))

			percent_compression = int((1.0 - (os.path.getsize(output_filename) / os.path.getsize(filename))) * 100 + 0.5)
			if percent_compression >= 0:
				message = f"{percent_compression}% size reduction"
			else:
				message = f"{-percent_compression}% size increase"
			console.message("Done: ", message, indent=2, color="green")
		elif opts.verbose:
			console.message("up-to-date", "", indent=2, color="green")

	print()
	print("Built %d and rebuilt %d of %d files." % (count_built, count_rebuilt, count_total))
	return 0
