all:

install:
	cp bin/* /usr/local/bin/

clean:
	rm -f tests/test_*.html tests/test_*.epub

commit:
	git push origin master


