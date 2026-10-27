import sys
import shutil
from typing import ClassVar

colors = {
	"red": "\033[91m",
	"green": "\033[92m",
	"yellow": "\033[93m",
	"blue": "\033[94m",
	"magenta": "\033[95m",
	"cyan": "\033[96m",
	"default": "\033[0m",
}

class Console:
	unicode_box_chars: ClassVar[str] = "┌─┐│─│└─┘"
	fallback_box_chars: ClassVar[str] = "+-+|-|+-++-+"
	def __init__(self):
		self.width = shutil.get_terminal_size(fallback=(80,24))[0]
		self.isatty = sys.stdout.isatty()
		try:
			self.unicode_box_chars.encode(sys.stdout.encoding)
			self.box_chars = self.unicode_box_chars
		except (UnicodeEncodeError, LookupError):
			self.box_chars = self.fallback_box_chars
	def banner(self, text, indent=0, color=None):
		tl, tm, tr, ml, mm, mr, bl, bm, br = self.box_chars
		width = self.width - 3 - indent
		padding = max(0, width - len(text))
		if color and self.isatty:
			sys.stdout.write(colors[color])
		print(" " * indent + tl + tm * width + tr)
		print(" " * indent + ml + text + " " * padding + mr)
		print(" " * indent + bl + bm * width + br)
		if color:
			sys.stdout.write(colors["default"])
	def message(self, prefix, message, color=None, indent=0, file=sys.stdout):
		if color is None or not self.isatty:
			color_start = color_end = ""
		else:
			color_start = colors[color]
			color_end = colors["default"]
		print(" " * indent + color_start + prefix + color_end + message, file=file)
	def warning(self, message, indent=0):
		self.message("Warning: ", message, color="yellow", indent=indent)
