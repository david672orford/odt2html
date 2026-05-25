# TODO

## Bugs

* Percentage font size in Header1 does not work correctly if Header sets a size.
  We need to go back along the line of descent to compute the size.
* Playing of audio fragments may not work on some browsers if the file is
  not encoded with a constant bitrate. Add automatic conformance testing.
* Table styles collide with paragraph styles. To demonstrate, try naming a
  table "Heading". It will aquire aspects of the paragraph style.
  This is because the paragraph styles use a .class selector. Should use
  P.class, H1.class, etc.

## Possible Improvements

* More complete style implementation including:
  * Document background color
  * More of the default paragraph style
* Drop page numbers from table of contents since they will be wrong even if
  the HTML file is printed from a browser
* Add something like subject\_index\_extractor.py to this project.
* Consider switching manifest format to https://schema.org/MediaObject

## Documentation Improvements

* Explain the use --docindex
* Explain the use of --template. Provide a sample template.
* Describe the Schema.org and Opengraph metadata handling
* Provide example command lines

