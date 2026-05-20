# TODO

## Bugs

* Percentage font size in Header1 does not work correctly if Header sets a size
* Playing of audio fragments may not work on some browsers if the file is
  not encoded with a constant bitrate. Add automatic conformance testing.

## Program Improvements

* Mixed ordered/unordered lists are not implemented.
  Should they be? (They aren't actually implemented in Libreoffice.)
* Style: Implement document background color
* Style: More complete conversion of the default paragraph style
* Drop page numbers from table of contents since they will be wrong even if
  the HTML file is printed from a browser
* Table styles collide with paragraph styles. To demonstrate, try naming a
  table "Heading".
* Add the topic index extractor to this project
* move html-index-odt here and rename it to odt2html-makeindex. Provide a default.
* move odt2pdf here as well
* Provide a sample template
* rename templates from filename.html.tmpl to filename-template.html

## Documentation Improvements

* Explain the use of HTML index files
* Describe the Schema.org and Opengraph metadata handling
* Provide example command lines

