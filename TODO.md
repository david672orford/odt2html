# TODO

## Bugs

* Frame anchored "to character" and floated right kills paragraph indent.
  At least it does in Chrome which splits the paragraph in two leaving the
  second part without a class and hence no style. May not be able to do anything
  about this, but we can print a warning.

## Program Improvements

* Mixed ordered/unordered lists are not implemented. Should they be?
* Implement document background color
* More complete conversion of the default paragraph style
* Reimplement style simplification:
  * Simplify more to make the CSS smaller
  * It would be nice if we no longer needed to offer different options
  * Paragraph styles which are functionally the same as their parents
    should be eliminated
  * Table cell borders should be simplified only if they are all the same.
  * Would it help to use something like SCCS?
* Figure out what ODF bookmarks are and whether we should implement them
* Drop page numbers from table of contents since they will be wrong even if
  the HTML file is printed from a browser
* Table styles collide with paragraph styles. To demonstrate, try naming a
  table "Heading".
* Playing of audio fragments may not work on some browsers if the file is
  not encoded with a constant bitrate. Add automatic conformance testing.
* Add the topic index extractor to this project
* Add ootool to this project
* Switch to argparse: https://gist.github.com/david672orford/9f0d41d41e5c1346bbe35d876e046aa8

## Documentation Improvements

* Better document use of HTML index files
* Document the Schema.org and Opengraph metadata handling
* Provide command examples
* Add example ODT files

