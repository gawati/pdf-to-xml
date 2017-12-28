#!/usr/bin/env python
from itertools import dropwhile
import sys
import os.path
import unicodedata
import string
from testprep_pdfdevice import PDFTextDevice
from testprep_pdffont import PDFUnicodeNotDefined
from testprep_layout import LTContainer, LTPage, LTText, LTLine, LTRect, LTCurve
from testprep_layout import LTFigure, LTImage, LTChar, LTTextLine, LTTextWord, LTImageBoxContainer,  LTExpandableContainer, LTTextColumn
from testprep_layout import LTTextBox, LTTextBoxVertical, LTTextGroup, LTTextColumnGroup
from testprep_utils import apply_matrix_pt, mult_matrix
from testprep_utils import enc, bbox2str
from math import ceil


##  PDFLayoutAnalyzer
##
class PDFLayoutAnalyzer(PDFTextDevice):

    def __init__(self, rsrcmgr, pageno=1, laparams=None):
        PDFTextDevice.__init__(self, rsrcmgr)
        self.pageno = pageno
        self.laparams = laparams
        self._stack = []
        return

    def begin_page(self, page, ctm):
        (x0, y0, x1, y1) = page.cropbox
        #(x0, y0) = apply_matrix_pt(ctm, (x0, y0))
        #(x1, y1) = apply_matrix_pt(ctm, (x1, y1))
        #mediabox = (0, 0, abs(x0-x1), abs(y0-y1))
        cropbox = page.cropbox
        self.cur_item = LTPage(self.pageno, cropbox)
        return

    def end_page(self, page):
        assert not self._stack
        assert isinstance(self.cur_item, LTPage)
        if self.laparams is not None:
            self.cur_item.analyze(self.laparams)
        self.pageno += 1
        self.receive_layout(self.cur_item)
        return

    def begin_figure(self, name, bbox, matrix):
        self._stack.append(self.cur_item)
        self.cur_item = LTFigure(name, bbox, mult_matrix(matrix, self.ctm))
        return

    def end_figure(self, _):
        fig = self.cur_item
        assert isinstance(self.cur_item, LTFigure)
        self.cur_item = self._stack.pop()
        self.cur_item.add(fig)
        return

    def render_image(self, name, stream):
        assert isinstance(self.cur_item, LTFigure)
        item = LTImage(name, stream,
                       (self.cur_item.x0, self.cur_item.y0,
                        self.cur_item.x1, self.cur_item.y1))
        self.cur_item.add(item)
        return

    def paint_path(self, gstate, stroke, fill, evenodd, path):
        shape = ''.join(x[0] for x in path)
        if shape == 'ml':
            # horizontal/vertical line
            (_, x0, y0) = path[0]
            (_, x1, y1) = path[1]
            (x0, y0) = apply_matrix_pt(self.ctm, (x0, y0))
            (x1, y1) = apply_matrix_pt(self.ctm, (x1, y1))
            if x0 == x1 or y0 == y1:
                self.cur_item.add(LTLine(gstate.linewidth, (x0, y0), (x1, y1)))
                return
        if shape == 'mlllh':
            # rectangle
            (_, x0, y0) = path[0]
            (_, x1, y1) = path[1]
            (_, x2, y2) = path[2]
            (_, x3, y3) = path[3]
            (x0, y0) = apply_matrix_pt(self.ctm, (x0, y0))
            (x1, y1) = apply_matrix_pt(self.ctm, (x1, y1))
            (x2, y2) = apply_matrix_pt(self.ctm, (x2, y2))
            (x3, y3) = apply_matrix_pt(self.ctm, (x3, y3))
            if ((x0 == x1 and y1 == y2 and x2 == x3 and y3 == y0) or
                (y0 == y1 and x1 == x2 and y2 == y3 and x3 == x0)):
                self.cur_item.add(LTRect(gstate.linewidth, (x0, y0, x2, y2)))
                return
        # other shapes
        pts = []
        for p in path:
            for i in xrange(1, len(p), 2):
                pts.append(apply_matrix_pt(self.ctm, (p[i], p[i+1])))
        self.cur_item.add(LTCurve(gstate.linewidth, pts))
        return

    def render_char(self, matrix, font, fontsize, fontcolor, scaling, rise, cid):
        try:
            text = font.to_unichr(cid)
            assert isinstance(text, unicode), text
        except PDFUnicodeNotDefined:
            text = self.handle_undefined_char(font, cid)
        textwidth = font.char_width(cid)
        textdisp = font.char_disp(cid)
        item = LTChar(matrix, font, fontsize, fontcolor, scaling, rise, text, textwidth, textdisp)
        self.cur_item.add(item)
        return item.adv

    def handle_undefined_char(self, font, cid):
        if self.debug:
            print >>sys.stderr, 'undefined: %r, %r' % (font, cid)
        return '(cid:%d)' % cid

    def receive_layout(self, ltpage):
        return


##  PDFPageAggregator
##
class PDFPageAggregator(PDFLayoutAnalyzer):

    def __init__(self, rsrcmgr, pageno=1, laparams=None):
        PDFLayoutAnalyzer.__init__(self, rsrcmgr, pageno=pageno, laparams=laparams)
        self.result = None
        return

    def receive_layout(self, ltpage):
        self.result = ltpage
        return

    def get_result(self):
        return self.result


##  PDFConverter
##
class PDFConverter(PDFLayoutAnalyzer):

    def __init__(self, rsrcmgr, outfp, codec='utf-8', pageno=1, laparams=None):
        PDFLayoutAnalyzer.__init__(self, rsrcmgr, pageno=pageno, laparams=laparams)
        self.outfp = outfp
        self.codec = codec
        return


##  TextConverter
##
class TextConverter(PDFConverter):

    def __init__(self, rsrcmgr, outfp, codec='utf-8', pageno=1, laparams=None,
                 showpageno=False, imagewriter=None):
        PDFConverter.__init__(self, rsrcmgr, outfp, codec=codec, pageno=pageno, laparams=laparams)
        self.showpageno = showpageno
        self.imagewriter = imagewriter
        return

    def write_text(self, text):
        self.outfp.write(text.encode(self.codec, 'ignore'))
        return

    def receive_layout(self, ltpage):
        def render(item):
            if isinstance(item, LTContainer):
                for child in item:
                    render(child)
            elif isinstance(item, LTText):
                self.write_text(item.get_text())
            if isinstance(item, LTTextBox):
                self.write_text('\n')
            elif isinstance(item, LTImage):
                if self.imagewriter is not None:
                    self.imagewriter.export_image(item)
        if self.showpageno:
            self.write_text('Page %s\n' % ltpage.pageid)
        render(ltpage)
        self.write_text('\f')
        return

    # Some dummy functions to save memory/CPU when all that is wanted
    # is text.  This stops all the image and drawing ouput from being
    # recorded and taking up RAM.
    def render_image(self, name, stream):
        if self.imagewriter is None:
            return
        PDFConverter.render_image(self, name, stream)
        return

    def paint_path(self, gstate, stroke, fill, evenodd, path):
        return


##  HTMLConverter
##
class HTMLConverter(PDFConverter):

    RECT_COLORS = {
        #'char': 'green',
        'figure': 'yellow',
        'textline': 'magenta',
        'textbox': 'cyan',
        'textgroup': 'red',
        'curve': 'black',
        'page': 'gray',
    }

    TEXT_COLORS = {
        'textbox': 'blue',
        'char': 'black',
    }

    def __init__(self, rsrcmgr, outfp, codec='utf-8', pageno=1, laparams=None,
                 scale=1, fontscale=1.0, layoutmode='normal', showpageno=True,
                 pagemargin=50, imagewriter=None,
                 rect_colors={'curve': 'black', 'page': 'gray'},
                 text_colors={'char': 'black'}):
        PDFConverter.__init__(self, rsrcmgr, outfp, codec=codec, pageno=pageno, laparams=laparams)
        self.scale = scale
        self.fontscale = fontscale
        self.layoutmode = layoutmode
        self.showpageno = showpageno
        self.pagemargin = pagemargin
        self.imagewriter = imagewriter
        self.rect_colors = rect_colors
        self.text_colors = text_colors
        if self.debug:
            self.rect_colors.update(self.RECT_COLORS)
            self.text_colors.update(self.TEXT_COLORS)
        self._yoffset = self.pagemargin
        self._font = None
        self._fontstack = []
        self.write_header()
        return

    def write(self, text):
        self.outfp.write(text)
        return

    def write_header(self):
        self.write('<html><head>\n')
        self.write('<meta http-equiv="Content-Type" content="text/html; charset=%s">\n' % self.codec)
        self.write('</head><body>\n')
        return

    def write_footer(self):
        self.write('<div style="position:absolute; top:0px;">Page: %s</div>\n' %
                   ', '.join('<a href="#%s">%s</a>' % (i, i) for i in xrange(1, self.pageno)))
        self.write('</body></html>\n')
        return

    def write_text(self, text):
        self.write(enc(text, self.codec))
        return

    def place_rect(self, color, borderwidth, x, y, w, h):
        color = self.rect_colors.get(color)
        if color is not None:
            self.write('<span style="position:absolute; border: %s %dpx solid; '
                       'left:%dpx; top:%dpx; width:%dpx; height:%dpx;"></span>\n' %
                       (color, borderwidth,
                        x*self.scale, (self._yoffset-y)*self.scale,
                        w*self.scale, h*self.scale))
        return

    def place_border(self, color, borderwidth, item):
        self.place_rect(color, borderwidth, item.x0, item.y1, item.width, item.height)
        return

    def place_image(self, item, borderwidth, x, y, w, h):
        if self.imagewriter is not None:
            name = self.imagewriter.export_image(item)
            self.write('<img src="%s" border="%d" style="position:absolute; left:%dpx; top:%dpx;" '
                       'width="%d" height="%d" />\n' %
                       (enc(name), borderwidth,
                        x*self.scale, (self._yoffset-y)*self.scale,
                        w*self.scale, h*self.scale))
        return

    def place_text(self, color, text, x, y, size):
        color = self.text_colors.get(color)
        if color is not None:
            self.write('<span style="position:absolute; color:%s; left:%dpx; top:%dpx; font-size:%dpx;">' %
                       (color, x*self.scale, (self._yoffset-y)*self.scale, size*self.scale*self.fontscale))
            self.write_text(text)
            self.write('</span>\n')
        return

    def begin_div(self, color, borderwidth, x, y, w, h, writing_mode=False):
        self._fontstack.append(self._font)
        self._font = None
        self.write('<div style="position:absolute; border: %s %dpx solid; writing-mode:%s; '
                   'left:%dpx; top:%dpx; width:%dpx; height:%dpx;">' %
                   (color, borderwidth, writing_mode,
                    x*self.scale, (self._yoffset-y)*self.scale,
                    w*self.scale, h*self.scale))
        return

    def end_div(self, color):
        if self._font is not None:
            self.write('</span>')
        self._font = self._fontstack.pop()
        self.write('</div>')
        return

    def put_text(self, text, fontname, fontsize):
        font = (fontname, fontsize)
        if font != self._font:
            if self._font is not None:
                self.write('</span>')
            self.write('<span style="font-family: %s; font-size:%dpx">' %
                       (fontname, fontsize * self.scale * self.fontscale))
            self._font = font
        self.write_text(text)
        return

    def put_newline(self):
        self.write('<br>')
        return

    def receive_layout(self, ltpage):
        def show_group(item):
            if isinstance(item, LTTextGroup):
                self.place_border('textgroup', 1, item)
                for child in item:
                    show_group(child)



        def render(item):
            if isinstance(item, LTPage):
                self._yoffset += item.y1
                self.place_border('page', 1, item)
                if self.showpageno:
                    self.write('<div style="position:absolute; top:%dpx;">' %
                               ((self._yoffset-item.y1)*self.scale))
                    self.write('<a name="%s">Page %s</a></div>\n' % (item.pageid, item.pageid))
                for child in item:
                    render(child)
                if item.groups is not None:
                    for group in item.groups:
                        show_group(group)
            elif isinstance(item, LTCurve):
                self.place_border('curve', 1, item)
            elif isinstance(item, LTFigure):
                self.begin_div('figure', 1, item.x0, item.y1, item.width, item.height)
                for child in item:
                    render(child)
                self.end_div('figure')
            elif isinstance(item, LTImage):
                self.place_image(item, 1, item.x0, item.y1, item.width, item.height)
            else:
                if self.layoutmode == 'exact':
                    if isinstance(item, LTTextLine):
                        self.place_border('textline', 1, item)
                        for child in item:
                            render(child)
                    elif isinstance(item, LTTextBox):
                        self.place_border('textbox', 1, item)
                        self.place_text('textbox', str(item.index+1), item.x0, item.y1, 20)
                        for child in item:
                            render(child)
                    elif isinstance(item, LTChar):
                        self.place_border('char', 1, item)
                        self.place_text('char', item.get_text(), item.x0, item.y1, item.size)
                else:
                    if isinstance(item, LTTextLine):
                        for child in item:
                            render(child)
                        if self.layoutmode != 'loose':
                            self.put_newline()
                    elif isinstance(item, LTTextBox):
                        self.begin_div('textbox', 1, item.x0, item.y1, item.width, item.height,
                                       item.get_writing_mode())
                        for child in item:
                            render(child)
                        self.end_div('textbox')
                    elif isinstance(item, LTChar):
                        self.put_text(item.get_text(), item.fontname, item.size)
                    elif isinstance(item, LTText):
                        self.write_text(item.get_text())
            return
        render(ltpage)
        self._yoffset += self.pagemargin
        return

    def close(self):
        self.write_footer()
        return


##  XMLConverter
##
class XMLConverter(PDFConverter):

    def __init__(self, rsrcmgr, outfp, codec='utf-8', pageno=1,
                 laparams=None, imagewriter=None, out_directory = None):
        PDFConverter.__init__(self, rsrcmgr, outfp, codec=codec, pageno=pageno, laparams=laparams)
        self.out_directory = out_directory
        self.imagewriter = imagewriter
        self.write_header()

        self.page_x0 = 0.0
        self.page_y0 = 0.0
        self.page_height = 0.0
        self.page_width = 0.0

        self.is_table = False
        self.table_index = 1

        self.is_column = False
        self.column_start_x_position = -60000
        self.column_end_x_position = -60000
        self.column_index = 1
        self.column_dict = []
        self.column_all_dict = []
        self.column_level = []
        self.column_running_index = 0

        self.closed_curve_index = 1
        self.closed_curves = {}
        self.is_closed_curve = False
        self.current_closed_curve_index = 0
        self.previous_curve = None
        self.current_curve = None

        self.current_flow_y = 0
        self.current_flow_x = 0

        self.reading_order = []
        self.sort_order = []

        self.para_status = False

        self.wmode = ' wmode="horizontal"'

        self.line_id = 1
        self.word_id = 1
        self.image_id = 1
        self.equation_id = 1;
        return

    def write_header(self):
        self.outfp.write('<?xml version="1.0" encoding="%s" ?>\n' % self.codec)
        self.outfp.write('<pages>\n')
        print "started writing the page..."
        return

    def write_footer(self):
        print "done writing extract xml for this page."
        self.outfp.write('</pages>\n')
        return

    def write_text(self, text):
        self.outfp.write(enc(text, self.codec))
        return

    def receive_layout(self, ltpage):


        def rindex(object_list, item):
            try:
                return dropwhile(lambda x: object_list[x] != item, reversed(xrange(len(object_list)))).next()
            except StopIteration:
                raise ValueError, 'Converter.py receive_layout method line nu. 453 : rindex failed since item not found in list'

        def show_group(item):

            if isinstance(item, LTTextBox):
                x0 = item.x0 - self.page_x0
                y0 = item.y0 - self.page_y0
                height = item.height
                width = item.width
                self.outfp.write('<textparaitem id="%d" sparse="%s"  x ="%0.2f" y ="%0.2f" height ="%0.2f" width ="%0.2f" />\n' %
                                 (item.index, str(item.sparse),x0, y0, height, width))
            elif isinstance(item, LTTextGroup):
                x0 = item.x0 - self.page_x0
                y0 = self.page_height - item.y0
                height = item.height
                width = item.width
                self.outfp.write('<textgroup x ="%0.2f" y ="%0.2f" height ="%0.2f" width ="%0.2f">\n' % (x0, y0, height, width))
                for child in item:
                    show_group(child)
                self.outfp.write('</textgroup>\n')

            elif isinstance(item, LTTextColumn):
                x0 = item.x0 - self.page_x0
                y0 = item.y0 - self.page_y0
                height = item.height
                width = item.width
                self.outfp.write('<textcolumn id="%d" x ="%0.2f" y ="%0.2f" height ="%0.2f" width ="%0.2f" />\n' %
                                 (item.index,x0, y0, height, width))



            elif isinstance(item, LTTextColumnGroup):
                x0 = item.x0 - self.page_x0
                y0 = self.page_height - item.y0
                height = item.height
                width = item.width
                self.outfp.write('<textcolumngroup x ="%0.2f" y ="%0.2f" height ="%0.2f" width ="%0.2f">\n' % (x0, y0, height, width))
                for child in item:
                    show_group(child)
                self.outfp.write('</textcolumngroup>\n')
            return

        def render(item):
            #print item
            if isinstance(item, LTPage):
                self.outfp.write('<page id="%s" cropbox="%s" x ="%0.2f" y ="%0.2f" height ="%0.2f" width ="%0.2f" rotate="%d">\n' %
                                 (item.pageid,(item.x0, item.y0, item.x1, item.y1), 0, 0, item.height, item.width, item.rotate))
                self.page_x0 = item.x0
                self.page_y0 = item.y0
                self.page_height = item.height
                self.page_width = item.width
                self.page_x1 = self.page_x0 + self.page_width
                self.page_y1 = self.page_y0 + self.page_height
                for child in item:
                    if child is not None:
                        x0 = int(child.x0) - int(self.page_x0)
                        y0 = int(self.page_height) - int(child.y0)
                        x1 = int(x0) + int(child.width)
                        y1 = int(y0) - int(child.height)
                        if isinstance(child, LTCurve):
                            if not x0 < 0.0 or x1 > self.page_width or y1 < 0.0 or y0 > self.page_height :
                                self.closed_curves[self.closed_curve_index] = (x0,y0,x1,y1)
                                self.closed_curve_index += 1
                            else:
                                pass
                        if isinstance(child, LTImageBoxContainer):
                            self.closed_curves[self.closed_curve_index] = (x0,y0,x1,y1)
                            self.closed_curve_index += 1
                        if isinstance(child, LTFigure):
                            self.closed_curves[self.closed_curve_index] = (x0,y0,x1,y1)
                            self.closed_curve_index += 1



                for child in item:

                    render(child)
                if(self.is_table == True):
                    self.outfp.write('</table>\n')
                    self.is_table == False
                if(self.is_column == True):
                    self.outfp.write('</column>\n')
                    self.is_column == False
                if(self.is_closed_curve == True):
                    #self.outfp.write('</box>\n')
                    self.is_closed_curve == False

                #if item.image_boxes is not None:
                 #   for image in item.image_boxes:
                  #      render(image)

                column_index = 0
                self.outfp.write('<columns>\n')
                for obj in self.column_all_dict :
                    self.outfp.write('\t<column id=\'%d\'>\n',column_index)
                    self.outfp.write('\t<x_start_position>')
                    self.outfp.write(obj)
                    self.outfp.write('\t</x_start_position>\n')
                    self.outfp.write('</column>\n')
                self.outfp.write('</columns>\n')

                self.outfp.write('<reading_order>\n')
                for obj in self.reading_order:
                    if obj is not '' and obj.find('table'):
                        self.outfp.write('\t<element>')
                        self.outfp.writelines(obj)
                        self.outfp.write('</element>\n')
                self.outfp.write('</reading_order>\n')
                #self.outfp.write('</page>\n')


                if item.groups is not None:
                    self.outfp.write('<layout>\n')
                    for group in item.groups:
                        show_group(group)
                    self.outfp.write('</layout>\n')
                self.outfp.write('</page>\n')


            elif isinstance(item, LTTextLine):
                x0 = item.x0
                y0 = self.page_height - item.y0
                width = item.width
                height = item.height
                if not(self.is_column or self.is_table) and self.para_status:
                    if("equation" in str(item.nature)):

                        if ("numeral" or "symbol" or "letter") in str(item.sparse):
                            if len(item._objs) == 1:
                                item.sparse = 'sparse'

                            self.outfp.write('<textline id="%d" nature="%s" continuation="true" type="100:0" sparse="%s" tag="p" x="%0.2f" y="%0.2f" height="%0.2f" width="%0.2f" number_of_words="%d">\n' %
                                             (self.line_id,str(item.nature), str(item.sparse), x0, y0, height, width, len(item._objs)))
                            obj = item._objs[0]
                            render(obj)
                            self.line_id += 1
                            self.outfp.write('</textline>\n')

                            x0 = x0 + obj.width + 1.5;

                        #print 'equation',x0,y0
                        self.outfp.write('<equation id="%d" name="equation%d" type="equation" x0="%0.2f" y0="%0.2f" x1="%0.2f" y1="%0.2f" />\n' %
                                         (self.equation_id, self.equation_id, x0, item.y0, item.x1, item.y1))
                        self.equation_id += 1
                    else:

                       # self.outfp.write('<textline id="%d" nature="%s" continuation="true" type="100:0" sparse="%s" tag="p" x="%0.2f" y="%0.2f" height="%0.2f" width="%0.2f">\n' %
                        #             (self.line_id,str(item.nature), str(item.sparse), x0, y0, height, width))

                        self.outfp.write('<textline id="%d" nature="%s" continuation="true" type="unassigned" sparse="%s" tag="p" x="%0.2f" y="%0.2f" height="%0.2f" width="%0.2f" number_of_words="%d">\n' %
                                     (self.line_id,str(item.nature), str(item.sparse), x0, y0, height, width, len(item._objs)))

                        for child in item:
                            render(child)
                        self.line_id += 1
                        self.outfp.write('</textline>\n')
            elif isinstance(item, LTTextWord):
                x0 = item.x0
                y0 = self.page_height - item.y0
                width = item.width
                height = item.height
                text = unicodedata.normalize('NFKC', unicode(self.filter_non_printable(item.get_text())))
                if self.wmode == ' wmode="horizontal"':
                    self.outfp.write('<textword id="%d" x="%0.2f" y="%0.2f" height="%0.2f" width="%0.2f" charspace="%0.2f">\n'
                                     %(self.word_id, x0, y0, height, width, item.char_space))
                else:
                    self.outfp.write('<textword id="%d" x="%0.2f" y="%0.2f" height="%0.2f" width="%0.2f" charspace="%0.2f">\n'
                                     %(self.word_id, x0, y0, width, height, item.char_space))

                self.outfp.write('<text>')
                #print item.get_text()
                #self.write_text(unicodedata.normalize('NFKC', unicode(self.filter_non_printable(item.get_text()))))
                self.write_text(self.filter_non_printable(item.get_text()))
                self.outfp.write('</text>\n')
                for child in item:
                        render(child)
                self.word_id += 1
                self.outfp.write('</textword>\n')
            elif isinstance(item, LTTextBox):
                #print 'textbox found'
                x0 = item.x0
                y0 = self.page_height - item.y0
                width = item.width
                height = item.height
                x1 = x0 + width
                y1 = y0 - height
                centroid_x = (x0 + width)/2
                centroid_y = (y0 - height)/2
                is_closed_content = False
                current_curve = None

                for curve in self.closed_curves:
                    (curve_x0, curve_y0, curve_x1, curve_y1) = self.closed_curves[curve]
                    if curve_x0 < x0 and x1 < curve_x1 and y0 < curve_y0 and y0 > curve_y1:
                        is_closed_content = True
                        current_curve = (curve_x0, curve_y0, curve_x1, curve_y1)

                if (self.previous_curve is not None and current_curve is not self.previous_curve and current_curve is not None) or ( self.previous_curve is not None and not is_closed_content):
                    if self.is_table:
                        self.outfp.write('</table>\n')
                        self.is_table == False
                    if self.is_column:
                        self.outfp.write('</column>\n')
                        self.is_column = False
                        self.column_start_x_position = -60000
                        self.column_end_x_position = 60000
                    #self.outfp.write('</box>\n')
                    self.is_closed_curve = False
                    self.current_curve = None
                    self.previous_curve = None
                if is_closed_content:
                    if self.is_table:
                        self.outfp.write('</table>\n')
                        self.is_table = False
                    if self.is_column:
                        self.outfp.write('</column>\n')
                        self.is_column = False
                        self.column_start_x_position = -60000
                        self.column_end_x_position = 60000
                    #self.is_closed_curve = True
                    self.column_level.append(y0)
                    #self.outfp.write('<box id="%d" curve="%s">\n' %(self.current_closed_curve_index, self.current_curve))
                    reading_dict_id = 'box-id:' + str(self.current_closed_curve_index)
                    self.current_closed_curve_index += 1
                    self.previous_curve = current_curve
                    key = 'box-' + str(current_curve)
                    if key in self.sort_order:
                        i = len(self.sort_order)
                        previous_sequence = rindex(self.sort_order, key)
                        j = previous_sequence + 2
                        self.sort_order.append("")
                        self.reading_order.append("")
                        if j == i+1:
                            self.sort_order[i] = key
                            self.reading_order[i] = reading_dict_id
                        elif j == i:
                            self.sort_order[i] = self.sort_order[i-1]
                            self.reading_order[i] = self.reading_order[i-1]
                            self.sort_order[j-1] = key
                            self.reading_order[j-1] = reading_dict_id
                        else:
                            while i > (j-1):
                                self.sort_order[i] = self.sort_order[i-1]
                                self.reading_order[i] = self.reading_order[i-1]
                                i -= 1
                            self.sort_order[j-1] = key
                            self.reading_order[j-1] = reading_dict_id
                    else:
                        self.sort_order.append(key)
                        self.reading_order.append((reading_dict_id))
                wmode = ''
                if isinstance(item, LTTextBoxVertical):
                    wmode = ' wmode="vertical"'
                else:
                    wmode = ' wmode="horizontal"'
                if self.current_flow_y > y0:
                    if self.is_table:
                        self.outfp.write('</table>\n')
                        self.is_table == False
                    if self.is_column:
                        self.outfp.write('</column>\n')
                        self.is_column = False
                        self.column_start_x_position = -60000
                        self.column_end_x_position = 60000
                if item.type == 'table' and not self.is_closed_curve:
                    if not self.is_table:
                        if self.is_column:
                            self.outfp.write('</column>\n')
                            self.is_column = False
                            self.column_start_x_position = -60000
                            self.column_end_x_position = 60000
                        self.column_level.append(y0)
                        self.outfp.write('<table id="%d">\n' % self.table_index)
                        reading_dict_id = 'table-id' + str(self.table_index)
                        self.table_index += 1
                        self.is_table = True
                        self.column_start_x_position = -60000
                        self.column_end_x_position = 60000
                        self.sort_order.append(reading_dict_id)
                        self.reading_order.append(reading_dict_id)
                else:
                    if self.is_table:
                        self.outfp.write('</table>\n')
                        self.is_table = False

                    if not((x0 <= self.column_start_x_position) or (x1 >= self.column_end_x_position) or self.column_start_x_position == -60000):
                        if self.column_index != 0 and self.is_column == True:
                            self.outfp.write('</column>\n')
                            self.is_column = False
                            self.column_start_x_position = -60000
                        self.column_end_x_position = 60000
                        self.outfp.write('<column id ="%d">\n')
                        reading_dict_id = 'column-id:' + str(self.column_index)
                        key = None
                        key_one = 'column-' + str(int(x0))
                        key_two = 'column-' + str(int(x0) + 1)
                        key_three = 'column-' + str(int(x0) - 1)
                        self.column_dict.append(self.column_index)
                        self.column_all_dict.append(x0)
                        self.column_level.append(y0)
                        self.column_index += 1
                        self.column_start_x_position = x0
                        self.column_end_x_position = x1
                        self.is_column = True
                        key_status = False
                        if not self.is_closed_curve:
                            if key_one in self.sort_order:
                                key = key_one
                                key_status = True
                            if key_two in self.sort_order:
                                key = key_two
                                key_status = True
                            if key_three in self.sort_order:
                                key = key_three
                                key_status = True
                            else:
                                key = key_one
                            if key_status:
                                previous_sequence = rindex(self.sort_order, key)
                                distance = y0 - self.column_level[previous_sequence]
                                if abs(distance) < (5 * item.height):
                                    if self.current_flow_x > x0:
                                        i = len(self.sort_order)
                                        previous_sequence = rindex(self.sort_order, key)
                                        j = previous_sequence + 2
                                        self.sort_order.append("")
                                        self.reading_order.append("")

                                        if j == i+1:
                                            self.sort_order[i] = key
                                            self.reading_order[i] = reading_dict_id
                                        elif j == i:
                                            self.sort_order[i] = self.sort_order[i-1]
                                            self.reading_order[i] = self.reading_order[i-1]
                                            self.sort_order[j-1] = key
                                            self.reading_order[j-1] = reading_dict_id
                                        else:
                                            while i > (j-1):
                                                self.sort_order[i] = self.sort_order[i-1]
                                                self.reading_order[i] = self.reading_order[i-1]
                                                i -= 1
                                            self.sort_order[j-1] = key
                                            self.reading_order[j-1] = reading_dict_id
                                    else:
                                        self.sort_order.append(key)
                                        self.reading_order.append(reading_dict_id)
                                else:
                                    self.sort_order.append(key)
                                    self.reading_order.append(reading_dict_id)
                            else:
                                self.sort_order.append(key)
                                self.reading_order.append(reading_dict_id)
                    else:
                        if not (x0 >= self.column_start_x_position) and (x0 <= self.column_end_x_position):
                            self.column_start_x_position = x0
                            self.column_end_x_position = x1
                self.para_status = True
                #if no item.sparse == 'equation':
                self.outfp.write('<textpara id="%d" sparse="%s" type="%s" %s x="%0.2f" y="%0.2f" height="%0.2f" width="%0.2f">\n' %(item.index, item.sparse, item.type, wmode, x0, y0, height, width))
                self.current_flow_x = x0
                self.current_flow_y = y0
                for child in item:
                    #print item
                    render(child)
                self.outfp.write('</textpara>\n'
                                 )
            elif isinstance(item, LTTextColumn):

                x0 = item.x0
                y0 = self.page_height - item.y0
                width = item.width
                height = item.height
                y1 = y0 - height
                x_centroid = (x0 + item.x1)/2
                x_centroid_diff = x_centroid - int(self.page_x0 + (self.page_width/2))
                #print x_centroid_diff
                if (abs(x_centroid_diff) <= (self.page_width/20)):
                    item.alignment = 'center'
                    #print 'center'
                elif x_centroid_diff >= 0:
                    item.alignment = 'right'
                else:
                    item.alignment = 'left'
                self.column_running_index += 1
                self.outfp.write('<column id="%d" x="%0.2f" y="%0.2f" height="%0.2f" width="%0.2f" alignment="%s">\n' %(self.column_running_index, x0, y0, height, width, item.alignment))
                item._objs.sort(key=lambda obj:(-obj.y0,obj.x0))
                for obj in item._objs:
                    render(obj)
                self.outfp.write('</column>\n')

                x0 = item.x0 - self.page_x0
                y0 = item.y0 - self.page_y0
                height = item.height
                width = item.width
                self.outfp.write('<textcolumn id="%d" x ="%0.2f" y ="%0.2f" height ="%0.2f" width ="%0.2f">\n' %
                                 (item.index,x0, y0, height, width))
                for child in item:
                    render(child)
                self.outfp.write('</textcolumn>\n')

            elif isinstance(item, LTTextColumnGroup):
                    x0 = item.x0 - self.page_x0
                    y0 = self.page_height - item.y0
                    height = item.height
                    width = item.width
                    #self.outfp.write('<textcolumngroup x ="%0.2f" y ="%0.2f" height ="%0.2f" width ="%0.2f">\n' % (x0, y0, height, width))

                    # for child in item:
                    #     render(child)
                    for child in item:
                        if isinstance(child, LTTextColumn):
                            render(child)
                    for child in item:
                        if isinstance(child, LTTextColumnGroup):
                            render(child)
                   # self.outfp.write('</textcolumngroup>\n')


            elif isinstance(item, LTChar):

                x0 = item.x0
                y0 = self.page_height - item.y0
                width = item.width
                height = item.height
                if self.para_status:
                    if self.wmode == ' wmode="horizontal"':
                        self.outfp.write('<glyph x="%0.2f" y="%0.2f" height="%0.2f" width="%0.2f" style="%s" alpha="%s">' %
                                 (x0, y0, height, width, item.style, item.textrotation))
                        #self.write_text(unicodedata.normalize('NFKC',unicode(self.filter_non_printable(item.get_text()))))
                        self.write_text(self.filter_non_printable(item.get_text()))
                        self.outfp.write('</glyph>\n')
                    else:
                        self.outfp.write('<glyph x="%0.2f" y="%0.2f" height="%0.2f" width="%0.2f" style="%s" alpha="%s">' %
                                         (x0, y0, width, height, item.fontname + ":"+ item.fontcolor + ":" + str(ceil(item.widths)), item.textrotation))
                        #self.write_text(unicodedata.normalize('NFKC',unicode(self.filter_non_printable(item.get_text()))))
                        self.write_text(self.filter_non_printable(item.get_text()))
                        self.outfp.write('</glyph>\n')
            elif isinstance(item, LTText):
                self.outfp.write('<glyph>%s</glyph>\n' % item.get_text())
            elif isinstance(item, LTImage):
                x0 = item.x0 - self.page_x0
                y0 = self.page_height - item.y1
                height = item.height
                width = item.width
                x1 = item.x0 - self.page_x0
                y1 = y0 - height


                if self.is_table:
                    self.outfp.write('</table>\n')
                    self.is_table = False
                else:
                    if self.is_column:
                        self.outfp.write('</column>\n')
                        self.is_column = False
                if self.is_closed_curve:
                    #self.outfp.write('</box>\n')
                    self.is_closed_curve = False


                if self.imagewriter is not None:
                    name = self.imagewriter.export_image(item)
                    self.outfp.write('<image id="%d" name="im%d" type="normal" src="%s" x="%0.2f" y="%0.2f" height="%0.2f" width="%0.2f" />\n' %
                                     (self.image_id, self.image_id, enc(name), item.x0, y0, item.height, item.width))
                else:
                    self.outfp.write('<image id="%d" name="im%d" type="normal" x="%0.2f" y="%0.2f" height="%0.2f" width="%0.2f" />\n' %
                                     (self.image_id, self.image_id, item.x0, y0, item.height, item.width))
                self.image_id += 1

            elif isinstance(item, LTLine):
                x0 = item.x0 - self.page_x0
                y0 = self.page_height - item.y0
                height = item.height
                width = item.width
                if self.is_table:
                    self.outfp.write('</table>\n')
                    self.is_table = False
                else:
                    if self.is_column:
                        self.outfp.write('</column>\n')
                        self.is_column = False
                if self.is_closed_curve:
                    #self.outfp.write('</box>\n')
                    self.is_closed_curve = False
                self.outfp.write('<vectorline id="%d" linewidth="%d" x0="%0.2f" y0="%0.2f" x1="%0.2f" y1="%0.2f" />\n' %
                                 (item.index, item.linewidth, item.x0, item.y0, item.x1, item.y1))
            elif isinstance(item, LTRect):
                x0 = item.x0 - self.page_x0
                y0 = self.page_height - item.y0
                height = item.height
                width = item.width
                if self.is_table:
                    self.outfp.write('</table>\n')
                    self.is_table = False
                else:
                    if self.is_column:
                        self.outfp.write('</column>\n')
                        self.is_column = False
                if self.is_closed_curve:
                    #self.outfp.write('</box>\n')
                    self.is_closed_curve = False
                if item.index is None :
                    item.index = 1
                self.outfp.write('<rect id="%d" linewidth="%d" x0="%0.2f" y0="%0.2f" x1="%0.2f" y1="%0.2f" />\n' %
                                 (item.index, item.linewidth, item.x0, item.y0, item.x1, item.y1))
            elif isinstance(item, LTCurve):
                x0 = item.x0 - self.page_x0
                y0 = self.page_height - item.y0
                height = item.height
                width = item.width
                if self.is_table:
                    self.outfp.write('</table>\n')
                    self.is_table = False
                else:
                    if self.is_column:
                        self.outfp.write('</column>\n')
                        self.is_column = False
                if self.is_closed_curve:
                    #self.outfp.write('</box>\n')
                    self.is_closed_curve = False
                self.outfp.write('<vectorcurve id="%d" linewidth="%d" x0="%0.2f" y0="%0.2f" x1="%0.2f" y1="%0.2f" />\n' %
                                 (item.index, item.linewidth, item.x0, item.y0, item.x1, item.y1))
            elif isinstance(item, LTFigure):
                x0 = item.x0 - self.page_x0
                y0 = self.page_height - item.y0
                height = item.height
                width = item.width
                if self.is_table:
                    self.outfp.write('</table>\n')
                    self.is_table = False
                else:
                    if self.is_column:
                        self.outfp.write('</column>\n')
                        self.is_column = False
                if self.is_closed_curve:
                    #self.outfp.write('</box>\n')
                    self.is_closed_curve = False
                self.outfp.write('<figure name="%s" x0="%0.2f" y0="%0.2f" x1="%0.2f" y1="%0.2f" >\n' %
                                 (item.name, item.x0, item.y0, item.x1, item.y1))
                for child in item:
                    render(child)
                self.outfp.write('</figure>\n')
            elif isinstance(item, LTImage):
                x0 = item.x0 - self.page_x0
                y0 = self.page_height - item.y0
                height = item.height
                width = item.width
                x1 = item.x0 - self.page_x0
                y1 = self.page_height - item.y1
                if self.is_table:
                    self.outfp.write('</table>\n')
                    self.is_table = False
                else:
                    if self.is_column:
                        self.outfp.write('</column>\n')
                        self.is_column = False
                if self.is_closed_curve:
                    #self.outfp.write('</box>\n')
                    self.is_closed_curve = False


                #if self.imagewriter is not None:
                  #  name = self.imagewriter.export_image(item)
                   # self.outfp.write('<image name="im%d" type="normal" src="%s" x0="%0.2f" y0="%0.2f" x1="%0.2f" y1="%0.2f" />\n' %
                    #                 (self.image_id, enc(name), item.x0, item.y0, item.x1, item.y1))
                #else:
                 #   self.outfp.write('<image name="im%d" x0="%0.2f" y0="%0.2f" x1="%0.2f" y1="%0.2f" />\n' %
                  #                   (self.image_id, item.x0, item.y0, item.x1, item.y1))

                #self.image_id += 1
            else:
                #print item
                pass
            return

        render(ltpage)
        return

    def filter_non_printable(self, str):
        return ''.join([c for c in str if ord(c) > 31 or ord(c) == 9])
    def close(self):
        self.write_footer()
        return


class LegalXMLConverter(PDFConverter):

    def __init__(self, rsrcmgr, outfp, codec='utf-8', pageno=1,
                 laparams=None, imagewriter=None, out_directory = None):
        PDFConverter.__init__(self, rsrcmgr, outfp, codec=codec, pageno=pageno, laparams=laparams)
        self.out_directory = out_directory
        self.imagewriter = imagewriter
        self.write_header()

        self.page_x0 = 0.0
        self.page_y0 = 0.0
        self.page_height = 0.0
        self.page_width = 0.0

        self.is_table = False
        self.table_index = 1

        self.is_column = False
        self.column_start_x_position = -60000
        self.column_end_x_position = -60000
        self.column_index = 1
        self.column_dict = []
        self.column_all_dict = []
        self.column_level = []
        self.column_running_index = 0

        self.closed_curve_index = 1
        self.closed_curves = {}
        self.is_closed_curve = False
        self.current_closed_curve_index = 0
        self.previous_curve = None
        self.current_curve = None

        self.current_flow_y = 0
        self.current_flow_x = 0

        self.reading_order = []
        self.sort_order = []

        self.para_status = False

        self.wmode = ' wmode="horizontal"'

        self.line_id = 1
        self.word_id = 1
        self.image_id = 1
        self.equation_id = 1;
        return

    def write_header(self):
        self.outfp.write('<?xml version="1.0" encoding="%s" ?>\n' % self.codec)
        self.outfp.write('<pages>\n')
        print "started writing the page..."
        return

    def write_footer(self):
        print "done writing extract xml for this page."
        self.outfp.write('</pages>\n')
        return

    def write_text(self, text):
        self.outfp.write(enc(text, self.codec))
        return

    def receive_layout(self, ltpage):


        def rindex(object_list, item):
            try:
                return dropwhile(lambda x: object_list[x] != item, reversed(xrange(len(object_list)))).next()
            except StopIteration:
                raise ValueError, 'Converter.py receive_layout method line nu. 453 : rindex failed since item not found in list'

        def show_group(item):

            if isinstance(item, LTTextBox):
                x0 = item.x0 - self.page_x0
                y0 = item.y0 - self.page_y0
                height = item.height
                width = item.width
                self.outfp.write('<textparaitem id="%d" sparse="%s"  x ="%0.2f" y ="%0.2f" height ="%0.2f" width ="%0.2f" />\n' %
                                 (item.index, str(item.sparse),x0, y0, height, width))
            elif isinstance(item, LTTextGroup):
                x0 = item.x0 - self.page_x0
                y0 = self.page_height - item.y0
                height = item.height
                width = item.width
                self.outfp.write('<textgroup x ="%0.2f" y ="%0.2f" height ="%0.2f" width ="%0.2f">\n' % (x0, y0, height, width))
                for child in item:
                    show_group(child)
                self.outfp.write('</textgroup>\n')

            elif isinstance(item, LTTextColumn):
                x0 = item.x0 - self.page_x0
                y0 = item.y0 - self.page_y0
                height = item.height
                width = item.width
                self.outfp.write('<textcolumn id="%d" x ="%0.2f" y ="%0.2f" height ="%0.2f" width ="%0.2f" />\n' %
                                 (item.index,x0, y0, height, width))



            elif isinstance(item, LTTextColumnGroup):
                x0 = item.x0 - self.page_x0
                y0 = self.page_height - item.y0
                height = item.height
                width = item.width
                self.outfp.write('<textcolumngroup x ="%0.2f" y ="%0.2f" height ="%0.2f" width ="%0.2f">\n' % (x0, y0, height, width))
                for child in item:
                    show_group(child)
                self.outfp.write('</textcolumngroup>\n')
            return

        def render(item):
            #print item
            if isinstance(item, LTPage):
                self.outfp.write('<page id="%s" cropbox="%s" x ="%0.2f" y ="%0.2f" height ="%0.2f" width ="%0.2f" rotate="%d">\n' %
                                 (item.pageid,(item.x0, item.y0, item.x1, item.y1), 0, 0, item.height, item.width, item.rotate))
                self.page_x0 = item.x0
                self.page_y0 = item.y0
                self.page_height = item.height
                self.page_width = item.width
                self.page_x1 = self.page_x0 + self.page_width
                self.page_y1 = self.page_y0 + self.page_height
                for child in item:
                    if child is not None:
                        x0 = int(child.x0) - int(self.page_x0)
                        y0 = int(self.page_height) - int(child.y0)
                        x1 = int(x0) + int(child.width)
                        y1 = int(y0) - int(child.height)
                        if isinstance(child, LTCurve):
                            if not x0 < 0.0 or x1 > self.page_width or y1 < 0.0 or y0 > self.page_height :
                                self.closed_curves[self.closed_curve_index] = (x0,y0,x1,y1)
                                self.closed_curve_index += 1
                            else:
                                pass
                        if isinstance(child, LTImageBoxContainer):
                            self.closed_curves[self.closed_curve_index] = (x0,y0,x1,y1)
                            self.closed_curve_index += 1
                        if isinstance(child, LTFigure):
                            self.closed_curves[self.closed_curve_index] = (x0,y0,x1,y1)
                            self.closed_curve_index += 1



                for child in item:

                    render(child)
                if(self.is_table == True):
                    self.outfp.write('</table>\n')
                    self.is_table == False
                if(self.is_column == True):
                    self.outfp.write('</column>\n')
                    self.is_column == False
                if(self.is_closed_curve == True):
                    #self.outfp.write('</box>\n')
                    self.is_closed_curve == False

                #if item.image_boxes is not None:
                 #   for image in item.image_boxes:
                  #      render(image)

                column_index = 0
                self.outfp.write('<columns>\n')
                for obj in self.column_all_dict :
                    self.outfp.write('\t<column id=\'%d\'>\n',column_index)
                    self.outfp.write('\t<x_start_position>')
                    self.outfp.write(obj)
                    self.outfp.write('\t</x_start_position>\n')
                    self.outfp.write('</column>\n')
                self.outfp.write('</columns>\n')

                self.outfp.write('<reading_order>\n')
                for obj in self.reading_order:
                    if obj is not '' and obj.find('table'):
                        self.outfp.write('\t<element>')
                        self.outfp.writelines(obj)
                        self.outfp.write('</element>\n')
                self.outfp.write('</reading_order>\n')
                #self.outfp.write('</page>\n')


                if item.groups is not None:
                    self.outfp.write('<layout>\n')
                    for group in item.groups:
                        show_group(group)
                    self.outfp.write('</layout>\n')
                self.outfp.write('</page>\n')


            elif isinstance(item, LTTextLine):
                x0 = item.x0
                y0 = self.page_height - item.y0
                width = item.width
                height = item.height
                if not(self.is_column or self.is_table) and self.para_status:
                    if("equation" in str(item.nature)):

                        if ("numeral" or "symbol" or "letter") in str(item.sparse):
                            if len(item._objs) == 1:
                                item.sparse = 'sparse'

                            self.outfp.write('<textline id="%d" nature="%s" continuation="true" type="100:0" sparse="%s" tag="p" x="%0.2f" y="%0.2f" height="%0.2f" width="%0.2f" number_of_words="%d">\n' %
                                             (self.line_id,str(item.nature), str(item.sparse), x0, y0, height, width, len(item._objs)))
                            obj = item._objs[0]
                            render(obj)
                            self.line_id += 1
                            self.outfp.write('</textline>\n')

                            x0 = x0 + obj.width + 1.5;

                        #print 'equation',x0,y0
                        self.outfp.write('<equation id="%d" name="equation%d" type="equation" x0="%0.2f" y0="%0.2f" x1="%0.2f" y1="%0.2f" />\n' %
                                         (self.equation_id, self.equation_id, x0, item.y0, item.x1, item.y1))
                        self.equation_id += 1
                    else:

                       # self.outfp.write('<textline id="%d" nature="%s" continuation="true" type="100:0" sparse="%s" tag="p" x="%0.2f" y="%0.2f" height="%0.2f" width="%0.2f">\n' %
                        #             (self.line_id,str(item.nature), str(item.sparse), x0, y0, height, width))

                        self.outfp.write('<textline id="%d" nature="%s" continuation="true" type="unassigned" sparse="%s" tag="p" x="%0.2f" y="%0.2f" height="%0.2f" width="%0.2f" number_of_words="%d">\n' %
                                     (self.line_id,str(item.nature), str(item.sparse), x0, y0, height, width, len(item._objs)))

                        for child in item:
                            render(child)
                        self.line_id += 1
                        self.outfp.write('</textline>\n')
            elif isinstance(item, LTTextWord):
                x0 = item.x0
                y0 = self.page_height - item.y0
                width = item.width
                height = item.height
                text = unicodedata.normalize('NFKC', unicode(self.filter_non_printable(item.get_text())))
                if self.wmode == ' wmode="horizontal"':
                    self.outfp.write('<textword id="%d" x="%0.2f" y="%0.2f" height="%0.2f" width="%0.2f" charspace="%0.2f">\n'
                                     %(self.word_id, x0, y0, height, width, item.char_space))
                else:
                    self.outfp.write('<textword id="%d" x="%0.2f" y="%0.2f" height="%0.2f" width="%0.2f" charspace="%0.2f">\n'
                                     %(self.word_id, x0, y0, width, height, item.char_space))

                self.outfp.write('<text>')
                #print item.get_text()
                #self.write_text(unicodedata.normalize('NFKC', unicode(self.filter_non_printable(item.get_text()))))
                self.write_text(self.filter_non_printable(item.get_text()))
                self.outfp.write('</text>\n')
                for child in item:
                        render(child)
                self.word_id += 1
                self.outfp.write('</textword>\n')
            elif isinstance(item, LTTextBox):
                #print 'textbox found'
                x0 = item.x0
                y0 = self.page_height - item.y0
                width = item.width
                height = item.height
                x1 = x0 + width
                y1 = y0 - height
                centroid_x = (x0 + width)/2
                centroid_y = (y0 - height)/2
                is_closed_content = False
                current_curve = None

                for curve in self.closed_curves:
                    (curve_x0, curve_y0, curve_x1, curve_y1) = self.closed_curves[curve]
                    if curve_x0 < x0 and x1 < curve_x1 and y0 < curve_y0 and y0 > curve_y1:
                        is_closed_content = True
                        current_curve = (curve_x0, curve_y0, curve_x1, curve_y1)

                if (self.previous_curve is not None and current_curve is not self.previous_curve and current_curve is not None) or ( self.previous_curve is not None and not is_closed_content):
                    if self.is_table:
                        self.outfp.write('</table>\n')
                        self.is_table == False
                    if self.is_column:
                        self.outfp.write('</column>\n')
                        self.is_column = False
                        self.column_start_x_position = -60000
                        self.column_end_x_position = 60000
                    #self.outfp.write('</box>\n')
                    self.is_closed_curve = False
                    self.current_curve = None
                    self.previous_curve = None
                if is_closed_content:
                    if self.is_table:
                        self.outfp.write('</table>\n')
                        self.is_table = False
                    if self.is_column:
                        self.outfp.write('</column>\n')
                        self.is_column = False
                        self.column_start_x_position = -60000
                        self.column_end_x_position = 60000
                    #self.is_closed_curve = True
                    self.column_level.append(y0)
                    #self.outfp.write('<box id="%d" curve="%s">\n' %(self.current_closed_curve_index, self.current_curve))
                    reading_dict_id = 'box-id:' + str(self.current_closed_curve_index)
                    self.current_closed_curve_index += 1
                    self.previous_curve = current_curve
                    key = 'box-' + str(current_curve)
                    if key in self.sort_order:
                        i = len(self.sort_order)
                        previous_sequence = rindex(self.sort_order, key)
                        j = previous_sequence + 2
                        self.sort_order.append("")
                        self.reading_order.append("")
                        if j == i+1:
                            self.sort_order[i] = key
                            self.reading_order[i] = reading_dict_id
                        elif j == i:
                            self.sort_order[i] = self.sort_order[i-1]
                            self.reading_order[i] = self.reading_order[i-1]
                            self.sort_order[j-1] = key
                            self.reading_order[j-1] = reading_dict_id
                        else:
                            while i > (j-1):
                                self.sort_order[i] = self.sort_order[i-1]
                                self.reading_order[i] = self.reading_order[i-1]
                                i -= 1
                            self.sort_order[j-1] = key
                            self.reading_order[j-1] = reading_dict_id
                    else:
                        self.sort_order.append(key)
                        self.reading_order.append((reading_dict_id))
                wmode = ''
                if isinstance(item, LTTextBoxVertical):
                    wmode = ' wmode="vertical"'
                else:
                    wmode = ' wmode="horizontal"'
                if self.current_flow_y > y0:
                    if self.is_table:
                        self.outfp.write('</table>\n')
                        self.is_table == False
                    if self.is_column:
                        self.outfp.write('</column>\n')
                        self.is_column = False
                        self.column_start_x_position = -60000
                        self.column_end_x_position = 60000
                if item.type == 'table' and not self.is_closed_curve:
                    if not self.is_table:
                        if self.is_column:
                            self.outfp.write('</column>\n')
                            self.is_column = False
                            self.column_start_x_position = -60000
                            self.column_end_x_position = 60000
                        self.column_level.append(y0)
                        self.outfp.write('<table id="%d">\n' % self.table_index)
                        reading_dict_id = 'table-id' + str(self.table_index)
                        self.table_index += 1
                        self.is_table = True
                        self.column_start_x_position = -60000
                        self.column_end_x_position = 60000
                        self.sort_order.append(reading_dict_id)
                        self.reading_order.append(reading_dict_id)
                else:
                    if self.is_table:
                        self.outfp.write('</table>\n')
                        self.is_table = False

                    if not((x0 <= self.column_start_x_position) or (x1 >= self.column_end_x_position) or self.column_start_x_position == -60000):
                        if self.column_index != 0 and self.is_column == True:
                            self.outfp.write('</column>\n')
                            self.is_column = False
                            self.column_start_x_position = -60000
                        self.column_end_x_position = 60000
                        self.outfp.write('<column id ="%d">\n')
                        reading_dict_id = 'column-id:' + str(self.column_index)
                        key = None
                        key_one = 'column-' + str(int(x0))
                        key_two = 'column-' + str(int(x0) + 1)
                        key_three = 'column-' + str(int(x0) - 1)
                        self.column_dict.append(self.column_index)
                        self.column_all_dict.append(x0)
                        self.column_level.append(y0)
                        self.column_index += 1
                        self.column_start_x_position = x0
                        self.column_end_x_position = x1
                        self.is_column = True
                        key_status = False
                        if not self.is_closed_curve:
                            if key_one in self.sort_order:
                                key = key_one
                                key_status = True
                            if key_two in self.sort_order:
                                key = key_two
                                key_status = True
                            if key_three in self.sort_order:
                                key = key_three
                                key_status = True
                            else:
                                key = key_one
                            if key_status:
                                previous_sequence = rindex(self.sort_order, key)
                                distance = y0 - self.column_level[previous_sequence]
                                if abs(distance) < (5 * item.height):
                                    if self.current_flow_x > x0:
                                        i = len(self.sort_order)
                                        previous_sequence = rindex(self.sort_order, key)
                                        j = previous_sequence + 2
                                        self.sort_order.append("")
                                        self.reading_order.append("")

                                        if j == i+1:
                                            self.sort_order[i] = key
                                            self.reading_order[i] = reading_dict_id
                                        elif j == i:
                                            self.sort_order[i] = self.sort_order[i-1]
                                            self.reading_order[i] = self.reading_order[i-1]
                                            self.sort_order[j-1] = key
                                            self.reading_order[j-1] = reading_dict_id
                                        else:
                                            while i > (j-1):
                                                self.sort_order[i] = self.sort_order[i-1]
                                                self.reading_order[i] = self.reading_order[i-1]
                                                i -= 1
                                            self.sort_order[j-1] = key
                                            self.reading_order[j-1] = reading_dict_id
                                    else:
                                        self.sort_order.append(key)
                                        self.reading_order.append(reading_dict_id)
                                else:
                                    self.sort_order.append(key)
                                    self.reading_order.append(reading_dict_id)
                            else:
                                self.sort_order.append(key)
                                self.reading_order.append(reading_dict_id)
                    else:
                        if not (x0 >= self.column_start_x_position) and (x0 <= self.column_end_x_position):
                            self.column_start_x_position = x0
                            self.column_end_x_position = x1
                self.para_status = True
                #if no item.sparse == 'equation':
                self.outfp.write('<textpara id="%d" sparse="%s" type="%s" %s x="%0.2f" y="%0.2f" height="%0.2f" width="%0.2f">\n' %(item.index, item.sparse, item.type, wmode, x0, y0, height, width))
                self.current_flow_x = x0
                self.current_flow_y = y0
                for child in item:
                    #print item
                    render(child)
                self.outfp.write('</textpara>\n'
                                 )
            elif isinstance(item, LTTextColumn):

                x0 = item.x0
                y0 = self.page_height - item.y0
                width = item.width
                height = item.height
                y1 = y0 - height
                x_centroid = (x0 + item.x1)/2
                x_centroid_diff = x_centroid - int(self.page_x0 + (self.page_width/2))
                #print x_centroid_diff
                if (abs(x_centroid_diff) <= (self.page_width/20)):
                    item.alignment = 'center'
                    #print 'center'
                elif x_centroid_diff >= 0:
                    item.alignment = 'right'
                else:
                    item.alignment = 'left'
                self.column_running_index += 1
                self.outfp.write('<column id="%d" x="%0.2f" y="%0.2f" height="%0.2f" width="%0.2f" alignment="%s">\n' %(self.column_running_index, x0, y0, height, width, item.alignment))
                item._objs.sort(key=lambda obj:(-obj.y0,obj.x0))
                for obj in item._objs:
                    render(obj)
                self.outfp.write('</column>\n')

                #x0 = item.x0 - self.page_x0
                #y0 = item.y0 - self.page_y0
                height = item.height
                width = item.width
                #self.outfp.write('<textcolumn id="%d" x ="%0.2f" y ="%0.2f" height ="%0.2f" width ="%0.2f">\n' %
                 #                (item.index,x0, y0, height, width))
                #for child in item:
                 #   render(child)
                #self.outfp.write('</textcolumn>\n')

            elif isinstance(item, LTTextColumnGroup):
                    x0 = item.x0 - self.page_x0
                    y0 = self.page_height - item.y0
                    height = item.height
                    width = item.width
                    #self.outfp.write('<textcolumngroup x ="%0.2f" y ="%0.2f" height ="%0.2f" width ="%0.2f">\n' % (x0, y0, height, width))

                    # for child in item:
                    #     render(child)
                    for child in item:
                        if isinstance(child, LTTextColumn):
                            render(child)
                    for child in item:
                        if isinstance(child, LTTextColumnGroup):
                            render(child)
                   # self.outfp.write('</textcolumngroup>\n')


            elif isinstance(item, LTChar):

                x0 = item.x0
                y0 = self.page_height - item.y0
                width = item.width
                height = item.height
                #if self.para_status:
                    #if self.wmode == ' wmode="horizontal"':
                     #   self.outfp.write('<glyph x="%0.2f" y="%0.2f" height="%0.2f" width="%0.2f" style="%s" alpha="%s">' %
                      #           (x0, y0, height, width, item.style, item.textrotation))
                        #self.write_text(unicodedata.normalize('NFKC',unicode(self.filter_non_printable(item.get_text()))))
                       # self.write_text(self.filter_non_printable(item.get_text()))
                        #self.outfp.write('</glyph>\n')
                    #else:
                     #   self.outfp.write('<glyph x="%0.2f" y="%0.2f" height="%0.2f" width="%0.2f" style="%s" alpha="%s">' %
                       #                  (x0, y0, width, height, item.fontname + ":"+ item.fontcolor + ":" + str(ceil(item.widths)), item.textrotation))
                        #self.write_text(unicodedata.normalize('NFKC',unicode(self.filter_non_printable(item.get_text()))))
                      #  self.write_text(self.filter_non_printable(item.get_text()))
                        #self.outfp.write('</glyph>\n')
            #elif isinstance(item, LTText):
             #   self.outfp.write('<glyph>%s</glyph>\n' % item.get_text())
            elif isinstance(item, LTImage):
                x0 = item.x0 - self.page_x0
                y0 = self.page_height - item.y1
                height = item.height
                width = item.width
                x1 = item.x0 - self.page_x0
                y1 = y0 - height


                if self.is_table:
                    self.outfp.write('</table>\n')
                    self.is_table = False
                else:
                    if self.is_column:
                        self.outfp.write('</column>\n')
                        self.is_column = False
                if self.is_closed_curve:
                    #self.outfp.write('</box>\n')
                    self.is_closed_curve = False


                if self.imagewriter is not None:
                    name = self.imagewriter.export_image(item)
                    self.outfp.write('<image id="%d" name="im%d" type="normal" src="%s" x="%0.2f" y="%0.2f" height="%0.2f" width="%0.2f" />\n' %
                                     (self.image_id, self.image_id, enc(name), item.x0, y0, item.height, item.width))
                else:
                    self.outfp.write('<image id="%d" name="im%d" type="normal" x="%0.2f" y="%0.2f" height="%0.2f" width="%0.2f" />\n' %
                                     (self.image_id, self.image_id, item.x0, y0, item.height, item.width))
                self.image_id += 1

            elif isinstance(item, LTLine):
                x0 = item.x0 - self.page_x0
                y0 = self.page_height - item.y0
                height = item.height
                width = item.width
                if self.is_table:
                    self.outfp.write('</table>\n')
                    self.is_table = False
                else:
                    if self.is_column:
                        self.outfp.write('</column>\n')
                        self.is_column = False
                if self.is_closed_curve:
                    #self.outfp.write('</box>\n')
                    self.is_closed_curve = False
                self.outfp.write('<vectorline id="%d" linewidth="%d" x0="%0.2f" y0="%0.2f" x1="%0.2f" y1="%0.2f" />\n' %
                                 (item.index, item.linewidth, item.x0, item.y0, item.x1, item.y1))
            elif isinstance(item, LTRect):
                x0 = item.x0 - self.page_x0
                y0 = self.page_height - item.y0
                height = item.height
                width = item.width
                if self.is_table:
                    self.outfp.write('</table>\n')
                    self.is_table = False
                else:
                    if self.is_column:
                        self.outfp.write('</column>\n')
                        self.is_column = False
                if self.is_closed_curve:
                    #self.outfp.write('</box>\n')
                    self.is_closed_curve = False
                if item.index is None :
                    item.index = 1
                self.outfp.write('<rect id="%d" linewidth="%d" x0="%0.2f" y0="%0.2f" x1="%0.2f" y1="%0.2f" />\n' %
                                 (item.index, item.linewidth, item.x0, item.y0, item.x1, item.y1))
            elif isinstance(item, LTCurve):
                x0 = item.x0 - self.page_x0
                y0 = self.page_height - item.y0
                height = item.height
                width = item.width
                if self.is_table:
                    self.outfp.write('</table>\n')
                    self.is_table = False
                else:
                    if self.is_column:
                        self.outfp.write('</column>\n')
                        self.is_column = False
                if self.is_closed_curve:
                    #self.outfp.write('</box>\n')
                    self.is_closed_curve = False
                self.outfp.write('<vectorcurve id="%d" linewidth="%d" x0="%0.2f" y0="%0.2f" x1="%0.2f" y1="%0.2f" />\n' %
                                 (item.index, item.linewidth, item.x0, item.y0, item.x1, item.y1))
            elif isinstance(item, LTFigure):
                x0 = item.x0 - self.page_x0
                y0 = self.page_height - item.y0
                height = item.height
                width = item.width
                if self.is_table:
                    self.outfp.write('</table>\n')
                    self.is_table = False
                else:
                    if self.is_column:
                        self.outfp.write('</column>\n')
                        self.is_column = False
                if self.is_closed_curve:
                    #self.outfp.write('</box>\n')
                    self.is_closed_curve = False
                self.outfp.write('<figure name="%s" x0="%0.2f" y0="%0.2f" x1="%0.2f" y1="%0.2f" >\n' %
                                 (item.name, item.x0, item.y0, item.x1, item.y1))
                for child in item:
                    render(child)
                self.outfp.write('</figure>\n')
            elif isinstance(item, LTImage):
                x0 = item.x0 - self.page_x0
                y0 = self.page_height - item.y0
                height = item.height
                width = item.width
                x1 = item.x0 - self.page_x0
                y1 = self.page_height - item.y1
                if self.is_table:
                    self.outfp.write('</table>\n')
                    self.is_table = False
                else:
                    if self.is_column:
                        self.outfp.write('</column>\n')
                        self.is_column = False
                if self.is_closed_curve:
                    #self.outfp.write('</box>\n')
                    self.is_closed_curve = False


                #if self.imagewriter is not None:
                  #  name = self.imagewriter.export_image(item)
                   # self.outfp.write('<image name="im%d" type="normal" src="%s" x0="%0.2f" y0="%0.2f" x1="%0.2f" y1="%0.2f" />\n' %
                    #                 (self.image_id, enc(name), item.x0, item.y0, item.x1, item.y1))
                #else:
                 #   self.outfp.write('<image name="im%d" x0="%0.2f" y0="%0.2f" x1="%0.2f" y1="%0.2f" />\n' %
                  #                   (self.image_id, item.x0, item.y0, item.x1, item.y1))

                #self.image_id += 1
            else:
                #print item
                pass
            return

        render(ltpage)
        return

    def filter_non_printable(self, str):
        return ''.join([c for c in str if ord(c) > 31 or ord(c) == 9])
    def close(self):
        self.write_footer()
        return
