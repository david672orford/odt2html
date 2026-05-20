class OdfException(Exception):
	"""Base of ODT converter exceptions"""

class OdfBadUsage(OdfException):
	"""Usage error"""

class OdfNotImplementedYet(OdfException):
	"""ODF feature not implemented"""

class OdfNotSupported(OdfException):
	"""Change unsupported formatting"""

class OdfInvalid(OdfException):
	"""ODT file is invalid"""

class OdfBadPlayer(OdfException):
	"""Bad player hyperlink"""

class OdfBadFormatting(OdfException):
	"""Dubious formatting would produce unacceptable result"""
