#!/usr/bin/env python
import sys
import os
from lc_pdfdocument import PDFDocument
from pdfminer.lc_pdfparser import PDFParser
from pdfminer.lc_pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.lc_pdfdevice import PDFDevice, TagExtractor
from pdfminer.lc_pdfpage import PDFPage
from pdfminer.lc_converter import XMLConverter, HTMLConverter, TextConverter
from pdfminer.lc_cmapdb import CMapDB
from pdfminer.lc_layout import LAParams
from pdfminer.lc_image import ImageWriter

__author__ = 'viveklal'


def main(argv):
    import getopt
    def usage():
        print ('usage: %s [-i input folder] [-o output folder]'
                % argv[0])
        return 100
    try:
        (opts, args) = getopt.getopt(argv[1:], 'i:o:')
    except getopt.GetoptError:
        return usage()

    # debug option
    debug = 0
    # input option
    password = ''
    pagenos = set()
    maxpages = 0
    # output option
    outfile = None
    outtype = None
    imagewriter = None
    rotation = 0
    layoutmode = 'normal'
    codec = 'utf-8'
    pageno = 1
    scale = 1
    caching = True
    showpageno = True
    laparams = LAParams()

    PDFDocument.debug = debug
    PDFParser.debug = debug
    CMapDB.debug = debug
    PDFResourceManager.debug = debug
    PDFPageInterpreter.debug = debug
    PDFDevice.debug = debug
    #
    rsrcmgr = PDFResourceManager(caching=caching)

    outtype = 'xml'


    for (k, v) in opts:
        if k == '-i': input_folder = v
        elif k == '-o': output_folder = v

    pdf_files = os.listdir(input_folder)

    for pdf_file in pdf_files :



        print 'PDF file name is -', pdf_file


        pdf_file_full_path = os.path.join(input_folder, pdf_file)

        outfile = output_folder + os.path.splitext(os.path.basename(pdf_file))[0] + '.xml'

        print 'Extracted output filename is -', outfile

        if outfile:
            outfp = file(outfile, 'w')
        else:
            outfp = sys.stdout
        device = XMLConverter(rsrcmgr, outfp, codec=codec, laparams=laparams,
                              imagewriter=imagewriter)
        fp = file(pdf_file_full_path, 'rb')
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        for page in PDFPage.get_pages(fp, pagenos,
                                      maxpages=maxpages, password=password,
                                      caching=caching, check_extractable=True):
            page.rotate = (page.rotate+rotation) % 360
            interpreter.process_page(page)
        fp.close()
        outfp.close()
    return

if __name__ == '__main__': sys.exit(main(sys.argv))