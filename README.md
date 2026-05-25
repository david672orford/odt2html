# Odt2html

This program converts Opendocument word-processing (ODT) files such as those
produced by Openoffice, Libreoffice, or Abiword into clean HTML files. It can
also produce e-books in EPUB format.

Odt2html is intended to be used in a workflow which produces documents for the
World Wide Web. It mplements a substantial subset of ODF formatting, but it is
not intended to convert all possible ODT files into a HTML, to precisely mimic
the print version, or to implement every feature. Openoffice and Libreoffice
already provide an export function which accomplishes this. Instead the emphasis
has been placed on producing straighforward and natural HTML which adapt to
screens and pages of various sizes.

While the implementation is not complete, it covers all of the standard
wordprocessing features including font changes, margins, tables, frames, images,
headers, footers, and endnotes. Images may be in in PNG, JPEG and drawings in SVG
format. ODF drawings are not implemented.

A number of extensions are provided:

* Conversion of user-specified frames into <nav> elements
* Zooming of selected images
* Conversion of selected tables into reflowable containers
* Clickable table cells which play sound
* A multimedia player which can be triggered by hyperlinks
* A moving highlighter driven by a VTT file

These extensions are described in more detail below.

## Usage

    odt2html [options] <filename.odt>...

      --verbose                     Show what files are being processed
      --debug                       Print debug messages
      --force                       Regenerate the output file even if the
                                    input file is not newer
      -o <directory>                Write HTML files to this directory, rather than dirctory of each ODT file
      --epub                        Break the output into one HTML file per
                                    section and wrap them in an EPUB file
      --warnings-formatting         List instances of direct formatting
      --font-support-level {0,1,2}  0=weight and slant, 1=generic families, 2=specified families
      --docdir=<filename>           User-provided HTML index of converted
      --template=<filename>         HTML file with <head> and body <body> material
                                    documents. Used to create "back" links.
                                    Also transfer Opengraph and Schema.org
                                    metadata from these indexes to the page.
      --site-name=<text>            Name of website for Opengraph metadata
      --site-url=<url>              Base URL of site for constructing page URLs
      --nav-names=<list>            Names of ODF frames which should be
                                    converted to <nav> elements rather than
                                    <div> elements
      --player-lib-dir=<directory>  Where will the media player files be on
                                    web server relative to the HTML file?

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
  the program will abort the conversion.

* Tabs for formatting tabular data are not supported in HTML. This
  converter will insert a few spaces for each tab, but unless the tabs
  are used for indenting the start of a line, things will not line up
  as you wished. Replace tabbed tables with actual tables. You can turn
  the borders off if you wish.

* Extra spaces which may have been inserted to shift line breaks will
  probably not produce the result you intended when the ODF file is
  converted to HTML. Even if it does, it will break when the window size is
  adjusted. Instead insert an explicit line break (shift-enter in
  Openoffice) or use non-breaking spaces undesirable breaks.

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
  Select the text in question, choose Format-&gt;Clear Direct Formatting, and
  then select the parts which should be superscripts or subscripts and again
  format them as such.

If you correct these problems you will get an HTML version which is
reasonably close to the printed or PDF version. But unlike the PDF
version it will be reflowed to suit the size of the viewer's window.
This generally works so well that documents originally formatted for
US Letter paper can be read conformatly on the screen of a smartphone.

## Incompatible Changes in Version 2.00

* --index is now --dirindex to avoid confusion with a document's topic index

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

## Formatting Adjustments for the Web

Odt2html uses a few CSS tricks improve reading on small screens. For one, the
margins are cut from 1/2" to 1/8" for narrow screens. Second, multi-column
layout is disabled for narrow screens.

## Spurious Span Tags in the HTML Output

Libreoffice is known to create large numbers of text spans when a document is
edited. At least some of these are to allow it to later display a history of
changes. This can be turned off by going to **Tools**, **Options**,
**LibreOffice Writer**, **Comparison**. Look for the heading **Random number
to improve accuracy of document comparision** and remove the checkbox
next to **Store it when changing the document**.

To remove these spans from existing documents, switch the default file format
used when saving to a non-extended version of ODF by going to **Tools**,
**Options**, **Load/Save**, **General**. Look for the heading **Default File
Format and ODF Settings** and change the **ODF format version** to one which
does not have "Extended" in its name.

## Handling of Hyperlinks to Audio and Video Files

If you put an hyperlink to an audio or video file in the ODT document and set
the **Target** to "player", Odt2html will create a popup player for it. (If you
do not set the target attribute, the browser will handle it however it thinks
best.)

The popup audio player takes the form of a horizontal bar at the bottom of the
screen which contains a play/pause button, a progress bar, a menu of download
links, and a close button.

The video player pops up in the middle of the window. It has a title bar
with download links and a close button. It can be dragged around the screen.

If you encoded your video file in multiple formats or video resolutions, the
player can select the most appropriate format. Supported formats include MP4,
WEBM, HTML, and DASH. Since Write does not provide a way to specify all the
necessary files, you use use **odt2html-mkmanifest** to create a JSON
manifest file. You can then select the manifest as the hyperlink target in
Write.

## Zoomable Images Extension

If you set the **Hyperlink** of an image to #zoom\_image, then the image will be
enlarged for easier viewing when the user clicks on it. This works best with
images which have sufficient resolution are are resolution-independent, such
as SVG drawings.

## Reflowable Grid Layout Extension

Odt2html provides an extension to the ODT format for creating grid layouts
which reflow displaying only as many columns as will fit on the page.
You can enable this feature by creating a table and including the substring
"Wrap" in its name. The cells will then flow into the available page much as
if they were words on a page or thumbnail images in a photo gallery.

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
  * If it is a directory, it should contain an audio file for each table cell.
    The names of the files without the extension should match the text of
    the cooresponding table cell. You should provide files in both MP3 and
    OGG formats.
  * If its is an Audacity labels file, it should contain labels that match the
    text in the same order as in the ODT file. There should be one MP3 and one
    OGG file alongside it (in the same directory) with the same base name.

If the text in a table cell (though of the correct language) does not match
a file in the directory specified or the next message in the Audacity labels
file, it will be skipped and that cell will not speak.

## Moving Highlight

TODO
