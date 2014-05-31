all:

install:
	cp odt2html /usr/local/bin/odt2html

clean:
	rm -f tests/test_*.html tests/test_*.epub

commit:
	git push origin master


