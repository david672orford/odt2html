from odt2html.dirindexes import Odt2HtmlDirectoryIndexes

class Odt2HtmlConfig:
	"""Container for the configuration"""

	debug:bool = False							# print details of the conversion process
	warnings_formatting:bool = False			# warn of instances of direct formatting
	error_unimplemented_tags:bool = True		# fail if unimplemented ODF tags are encountered
	output_format:str = "html"					# "html" or "epub"
	minimize_resources:bool = False				# minimize CSS and Javascript
	template:str|None = None					# HTML file with <head> and <header> boilerplate to add
	site_name:str|None = None					# --site-name=
	site_url:str|None = None					# --site-url=
	nav_names = []								# --nav-names=
	dirindexes = Odt2HtmlDirectoryIndexes()		# --dirindex=
	player_lib_dir:str = "../odt2html/assets"	# --player-lib-dir=
	player_version:str = "-v14.min"
	zoom_image_version:str = "-v1"

	# If False, then only one HTML file will be generated.
	# If True, then one HTML file will be generated for
	# each top-level <text:section>.
	split_by_sections:bool = False

	# Use data: URLs for embedded images?
	use_data_urls:bool = True

	# If the ODT file contains a table or contents, should we keep it?
	keep_toc:bool = True

	# 0: weight and slant, 1: generic families, 2: specified families
	font_support_level:int = 1

	# Convert SVG files to PNG files?
	svg2png:bool = False

	# Should we drop styles from the ODT file which are not used in the text?
	# FIXME: does not work correctly
	drop_unused_styles:bool = True

	# Openoffice uses unnecessarily complicated table border styles.
	# Even though the borders of ajoining cells should collapse,
	# it takes great care to define a border for only one of the
	# cells.
	simplify_table_borders:bool = False

	# Take tables which contain "Wrap" in their names and turn them into
	# wrappable containers of boxes.
	wrap_box_tables:bool = True
