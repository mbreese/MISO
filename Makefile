
all: Rpackage Pythonpackage

########################################################

RSRC=$(wildcard src/*.c) $(wildcard src/*.h) $(wildcard src/*.pmt)
RSRC2=$(patsubst src/%,splicing/src/%,$(RSRC))
RSRC3=$(wildcard splicing/R/*.R) $(wildcard splicing/man/*.Rd) $(wildcard splicing/src/*.c) splicing/src/Makevars.in

Rpackage: splicing_0.1.tar.gz

splicing_0.1.tar.gz: $(RSRC2) $(RSRC3) splicing/DESCRIPTION splicing/NAMESPACE
	cd splicing && autoconf && autoheader
	R CMD build splicing

splicing/src/%.c: src/%.c
	cp src/$(@F) $@

splicing/src/%.h: src/%.h
	cp src/$(@F) $@

splicing/src/%.pmt: src/%.pmt
	cp src/$(@F) $@

tests: Rtests Pythontests

Rtests:
	cd splicing/tests && echo "tools:::.runPackageTestsR()" | \
        R --no-save && echo

Pythontests:
	cp miso/test.py /tmp && cd /tmp && python test.py

########################################################

PSRC = $(wildcard src/*.c)
PSRC2 = $(wildcard src/*.h) $(wildcard src/*.pmt)
PSRC3 = $(patsubst src/%,miso/src/%,$(PSRC))
PSRC4 = $(patsubst src/%,miso/include/%,$(PSRC2))
PSRC5 = $(wildcard miso/miso/*.py)
PSRC6 = $(wildcard miso/src/*.c) $(wildcard miso/include/*.h) \
	$(wildcard miso/src/lapack/*.c) \
	$(wildcard miso/src/f2c/*.c)

Pythonpackage: miso-1.0.tar.gz

miso-0.1.tar.gz: $(PSRC3) $(PSRC4) $(PSRC5) $(PSRC6) miso/setup.py miso/MANIFEST.in
	rm -f miso/MANIFEST
	cd miso && python setup.py sdist -d ..

miso/src/%.c: src/%.c
	cp src/$(@F) $@

miso/include/%.h: src/%.h
	cp src/$(@F) $@

miso/include/%.pmt: src/%.pmt
	cp src/$(@F) $@

.PHONY: all Rpackage tests Rtests Pythonpackage Pythontests
