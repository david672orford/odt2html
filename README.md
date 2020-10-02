# Odt2html

This program converts Opendocument word-processing files such as those
produced by Openoffice into clean HTML files. It can also produce ebooks
in Epub format.

Odt2html is not intended to convert all possible ODT files into a visually
identical HTML representation. Openoffice and Libreoffice already provide
such a function. Instead it is intended to be used with documents which
were formatted with eventual conversion to HTML in mind. With care documents
can be formatted so that they will look good both in print and on the web.

## Usage

    odt2html [--debug] [--force] [--epub] <filename.odt>...
 
      --verbose                     show what files are being processed
      --debug                       print debug messages
      --force                       regenerate the output file even if the input file is
                                    not newer
      --epub                        break the output into one HTML file per section and
                                    wrap them in an EPUB file
      --template=<filename>         skeletal HTML file into which to insert converted document
      --site-name=<text>            name of website for Opengraph metadata
      --site-url=<url>              base URL of site for constructing page URLs
      --index=<filename>            get site metadata and first breadcrumb from this file
      --nav-names=<list>            names of ODF frames which should be <nav> rather than <div>
      --player-lib-dir=<directory>  where are the media player files?

Each input ODT file is converted to a single HTML or EPUB file. The output
file will have the same base name and will be placed in the same directory.

## Formatting with HTML Conversion in Mind

To get good results from Odt2html it is important avoid two kinds of formatting.
The first is formatting which has no clean HTML equivalent. Some examples
will be given below. The second thing to avoid is fragile formatting.
Fragile formatting is easy to create but creates more work later on.

A common example of fragile formatting is adding and removing spaces and
carriage returns in order nudge the page elements into their proper
positions. This is OK for some documents such as business letters which
will never be edited again, but not for documents which will be edited
repeatedly or converted into various formats with different page sizes.
Whenever text is inserted or deleted or margins, page size, or font size
are changed the text shifts around the the extra spaces and carriage
returns no longer do what they were supposed to do.

To create robust formatting we must seek out and use more advanced features
of the word processor. These features allow us to communicate our intent so
that the word processor can act accordingly as things shift around on the
page. Rather than using hard carriage returns and page breaks we can use
formatting features such as "keep together" and non-breaking spaces.

Here are some specific formatting suggestions. Following them will
ensure your document looks good both when printed and on the web.

* This program needs to know your document's title. It will look first
  in the metadata (go to File-&gt;Properties and look under the Description
  tab). If the title there is blank, it will look for level 1 headings
  and take the first one as the title. If there are no level 1 headings,
  the program will stop.

* Tabs for formatting tabular data are not supported in HTML. This
  converter will insert a few spaces for each tab, but unless the tabs
  are used for indenting the start of a line, things will not line up
  as you wished. Replace tabbed tables with actual tables. You can turn
  the borders off if you wish.

* Extra spaces which may have been inserted to shift line breaks will
  probably not produce the result you intended when the ODF file is
  converted to HTML. Even if it does, it will break when the window size is
  adjusted. Instead insert an explicit line break (shift-enter in
  Openoffice) or use non-breaking spaces to prevent a line break at an
  undesireable place.

* Likewise, if you inserted extra carriage returns (empty paragraphs)
  in order to change a page break, the result will look bad in the
  HTML version. There are no pages in a web browser, so you will get
  an ugly vertical gap in the document. To fix it, open the document in
  in Libreoffice Writer, place the cursor anywhere in the paragraph before
  the undesired break, go to Format-&gt;Paragraph and in the Text Flow tab
  check the box labeled "Keep with next paragraph". This will not only
  preserve the appearance of the HTML version, but it will fix the bad
  break permanently in the print and PDF versions.

* If you have indented single-line paragraphs using spaces or tabs, perhaps
  to represent a verse from a poem, you should reformat them to use a left
  margin. Otherwise when the lines are wrapped on a narrow display, they
  may become difficult to read. You may want to use a hanging indentation.
  Create a hanging indent by setting a left margin on the paragraph and a
  negative first-line margin.

* Watch out for superscripts and subscripts. In ODF format you can put a run
  of normal text inside a run of superscript or subscript text. HTML has no
  provision for this. It would be very tricky for Odt2html to unnest the
  spans, so instead you are expected to fix it in the source document.
  Select the text in question, chose Format-&gt;Clear Direct Formatting, and
  then select the parts which should be superscripts or subscripts and again
  format them as such.

If you correct these problems you will get an HTML version which is
reasonably close to the printed or PDF version. But unlike the PDF
version it will be reflowed to suit the size of the viewer's window.
This generally works so well that documents originally formatted for
US Letter paper can be read conformatly on the screen of a smartphone.

## Supported ODF Features

* Headings
* Paragraph indentation
* Font changes including family, weight, slant, superscript, subscript
* Text color (forground and background)
* Styles
* Tables with borders and padding
* Frames
* Ordered and unordered Lists
* Hyperlinks
* Raster images in JPEG, GIF, and PNG formats
* Vector drawings in SVG format
* Multiple columns

## No Plans to Support 

* Embedded Openoffice drawings (we suggest you use SVG instead)
* Tabs (not supported in HTML)
* Individual column widths in multi-column sections (not supported in HTML)

## Inter-Document Hyperlinks

If you create hyperlinks between documents in a set and then convert them
all to HTML using this program, the hyperlinks will be converted to link
to the HTML versions rather than to the original ODT documents.

## Master Documents

To convert a master document, open it in the word processor and exported it as
an ODT file and convert that. Hyperlinks between the subdocuments of a master
document will be converted to internal links within the final document.

## Formatting Adjustements for the Web

Odt2html uses a few CSS tricks improve reading on small screens. For one, the
margins are cut from 1/2" to 1/8" for narrow screens. Second, multi-column
layout is disabled for narrow screens.

# Handling of Hyperlinks to Audio and Video Files

If you put an hyperlink to an audio or video file in the ODT document and set
the "Target" to "player", Odt2html will create a popup player for it. (If you
do not set the target attribute, the browser will handle it however it thinks
best.)

The popup audio player takes the form of a horizontal bar at the bottom of the
screen which contains a play/pause button, a progress bar, a menu of download
links, and a close button.

The video player pops up in the middle of the window. It has a title bar
with download links and a close button. It can be dragged around the screen.

If you have media files in multiple formats or video resolutions, you should
create a manifest file using odt2html-media-manifest and point the hyperlink
to that.

## Speaking Table Cells Extension

Odt2html provides an extension to the ODT format for creating language
phrasebooks with spoken audio. Table cells which contain foreign language
phrases can be made to play individual audio files or segments of a single
single large audio file when the user clicks on them.

To set a document up for speaking table cells, create a user defined variable
in the document properties called "TD Sound" with the type "Text". The value
should be two values separated by a colon:

* A two-letter language code. If a table cell starts with a run of text
  marked as being in this language, it is considered to be an candidate for
  a speaking table cell. (You may used an asterisk as a wildcard.)
* A file system path relative to the ODT file. It should point either to a
  directory or to an Audacity labels file with an extension of .txt.
 * If it is a directory, it should contain audio files for each table cell.
   The names of the files without the extension should match the text of
   the cooresponding table cell. You should provide files in both MP3 and
   OGG formats.
 * If its is an Audacity labels file, it should contain labels that match the
   text in the same order as in the ODT file. There should be one MP3 and one
   OGG file alongside it with the same base name.

If the text in a table cell (though of the correct language) does not match
a file in the directory specified or the next message in the Audacity labels
file, it will be skipped and that cell will not speak.

## Reflowable Grid Layout Extension

Odt2html provides an extension to the ODT format for creating grid layouts
which reflow displaying only as many columns as will fit on the page.
You can enable this feature by creating a table and including the substring
"Wrap" in its name. The cells will then flow into the available page much as
if they were words on a page or thumbnail images in a photo gallery.

