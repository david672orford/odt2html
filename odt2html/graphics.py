import math
from dataclasses import dataclass

import lxml.etree as ET
from lxml.builder import E

from odt2html.utils import dimension2points
from odt2html.exceptions import OdfNotImplementedYet

@dataclass
class Elipse:
	cx: float
	cy: float
	rx: float
	ry: float
	def point(self, angle:float):
		angle = math.radians(-angle)
		return (
			self.cx + self.rx * math.cos(angle),
			self.cy + self.ry * math.sin(angle)
		)

@dataclass
class PathCmd:
	svg_code: str
	svg_code2: str|None
	nargs: int
	def convert(self, cmd:str, args:list[int], repeated:bool) -> str:
		return " ".join([self.svg_code2 if repeated else self.svg_code] + [str(arg) for arg in args])

class PathCmdTU(PathCmd):
	def convert(self, cmd:str, args:list[int], repeated:bool) -> str:
		cx, cy, rx, ry, start_angle, end_angle = args

		elipse = Elipse(cx, cy, rx, ry)
		x1, y1 = elipse.point(start_angle)

		svg_path = []
		if cmd == "U":
			svg_path.append(f"M {x1} {y1}")

		if abs(end_angle - start_angle) in (0, 360):
			x2, y2 = elipse.point(end_angle + 180)
			svg_path.append(f"A {rx} {ry} 0 0 0 {x2} {y2}")
			svg_path.append(f"A {rx} {ry} 0 0 0 {x1} {y1}")
		else:
			x2, y2 = elipse.point(end_angle)
			delta_angle = end_angle - start_angle
			if delta_angle < 0:
				delta_angle += 360
			large_arc = 1 if delta_angle > 180 else 0
			sweep = 0
			svg_path.append(f"A {rx} {ry} 0 {large_arc} {sweep} {x2} {y2}")
		return " ".join(svg_path)

path_cmds = {
	"C": PathCmd(svg_code="C", svg_code2="C", nargs=6),
	"L": PathCmd(svg_code="L", svg_code2="L", nargs=2),
	"M": PathCmd(svg_code="M", svg_code2="L", nargs=2),
	"T": PathCmdTU(svg_code="A", svg_code2="A", nargs=6),
	"U": PathCmdTU(svg_code="A", svg_code2="A", nargs=6),
	"Z": PathCmd(svg_code="Z", svg_code2=None, nargs=0),
}

def convert_custom_shape(odt_shape:ET._Element, debug:bool) -> ET._Element:
	# References:
	# * https://docs.oasis-open.org/office/OpenDocument/v1.3/os/part3-schema/OpenDocument-v1.3-os-part3-schema.html#attribute-draw_enhanced-path
	# * https://developer.mozilla.org/en-US/docs/Web/SVG/Tutorials/SVG_from_scratch/Paths
	# * https://www.svggenie.com/blog/svg-path-commands-complete-guide
	# * https://wiki.documentfoundation.org/images/f/ff/Custom-Shape-Tutorial.pdf
	assert odt_shape.tag == "draw:custom-shape"
	if debug:
		print(f"Custom shape: {repr(odt_shape.attrib)}")

	x = odt_shape.attrib["svg:x"]
	y = odt_shape.attrib["svg:y"]
	svg:ET._Element = E.svg({
		"id": odt_shape.attrib["draw:name"],
		"class": "graphic",
		"style": f"position: absolute; left: {x}; top: {y}; background-color: yellow",
		"width": odt_shape.attrib["svg:width"],
		"height": odt_shape.attrib["svg:height"],
		"preserveAspectRatio": "none",
		})

	for child in odt_shape:
		print("child:", child.tag, child.attrib)
		if child.tag == "draw:enhanced-geometry":
			svg.attrib["viewBox"] = child.attrib["svg:viewBox"]
			odf_path = child.attrib["draw:enhanced-path"].split()	# FIXME: spaces may sometimes be omitted
			svg_path = []
			while(len(odf_path)):
				cmd = odf_path.pop(0)
				print("cmd:", cmd)
				print("odf_path:", odf_path)
				if (cmdobj := path_cmds.get(cmd)) is not None:
					repeated = False
					while True:
						args, odf_path = odf_path[:cmdobj.nargs], odf_path[cmdobj.nargs:]
						args = [0 if arg[0]=="?" else int(arg) for arg in args]
						svg_path.append(cmdobj.convert(cmd, args, repeated))
						if len(odf_path) < cmdobj.nargs or odf_path[0][0].isalpha():
							break
						repeated = True
				elif cmd in ("N","F"):
					pass
				else:
					raise OdfNotImplementedYet(f"Enhanced path cmd {cmd}")
			svg.append(E.path({
				"d": " ".join(svg_path),
				"stroke": "black",
				"stroke-width": "100",
				"fill": "none",
				}))


	return svg

def convert_rect(odt_shape:ET._Element, debug:bool) -> ET._Element:
	assert odt_shape.tag == "draw:rect"
	if debug:
		print(f"Rectangle: {repr(odt_shape.attrib)}")
	width = odt_shape.attrib["svg:width"]
	height = odt_shape.attrib["svg:height"]
	x = odt_shape.attrib["svg:x"]
	y = odt_shape.attrib["svg:y"]
	svg:ET._Element = E.svg({
		"id": odt_shape.attrib["draw:name"],
		"class": "graphic",
		"style": f"position: absolute; left: {x}; top: {y}; background-color: yellow",
		"width": width,
		"height": height,
		"viewBox": f"0 0 {width} {height}",
		})
	svg.append(E.rect({
		"width": width,
		"height": height,
		"stroke": "black",
		"stroke-width": "5",
		"fill": "none",
		}))
	return svg

def convert_line(odt_shape:ET._Element, debug:bool) -> ET._Element:
	assert odt_shape.tag == "draw:line"
	if debug:
		print(f"Line: {repr(odt_shape.attrib)}")
	x1 = dimension2points(odt_shape.attrib["svg:x1"])
	y1 = dimension2points(odt_shape.attrib["svg:y1"])
	x2 = dimension2points(odt_shape.attrib["svg:x2"])
	y2 = dimension2points(odt_shape.attrib["svg:y2"])
	print("before:", x1, y1, x2, y2)
	minx = min(x1, x2)
	miny = min(y1, y2)
	x1 -= minx
	y1 -= miny
	x2 -= minx
	y2 -= miny
	print("after:", x1, y1, x2, y2)
	width = abs(x2 - x1)
	height = abs(y2 - y1)
	print("size:", width, height)
	svg:ET._Element = E.svg({
		"id": odt_shape.attrib["draw:name"],
		"class": "graphic",
		"style": f"position: absolute; left: {minx}; top: {miny}; background-color: yellow",
		"width": f"{width}pt",
		"height": f"{height}pt",
		"viewBox": f"0 0 {width}pt {height}pt",
		})
	svg.append(E.line({
		"x1": f"{x1}pt",
		"y1": f"{y1}pt",
		"x2": f"{x2}pt",
		"y2": f"{y2}pt",
		"stroke": "black",
		"stroke-width": "1",
		}))
	return svg
