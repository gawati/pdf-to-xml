#!/usr/bin/env python
import sys
import re



from testprep_utils import INF, Plane, get_bound, uniq, csort, fsplit
from testprep_utils import bbox2str, matrix2str, apply_matrix_pt
from collections import namedtuple
import math
from math import ceil, sqrt
from testprep_psparser import LIT



object_dictionary = {}

##  Constants
##
NORMAL_LINE = 'normal line'
TABLE_LINE = 'table line'
HEADER_LINE = 'header line'
LIST_LINE_NUMERAL_TYPE = 'list line numeral type'
LIST_LINE_LETTER_TYPE =  'list line letter type'
LIST_LINE_SYMBOL_TYPE =  'list line symbol type'
LIST_LINE_UNMARKED_TYPE =  'list line unmarked type'
LIST_LINE_PARENTHESIS_TYPE = 'list line parenthesis text'

DEFAULT_TEXT_COLOR_BLACK ='#000000'

is_formula_page = False


##  IndexAssigner
##
class IndexAssigner(object):
    def __init__(self, textbox_index=1, curve_index=1, image_index=1, rect_index=1, column_index = 1):
        self.textbox_index = textbox_index
        self.curve_index = curve_index
        self.image_index = image_index
        self.rect_index = rect_index
        self.column_index = column_index
        return

    def run(self, obj):
        if isinstance(obj, LTTextBox):
            obj.index = self.textbox_index
            self.textbox_index += 1
        elif isinstance(obj, LTTextGroup):
            for x in obj:
                self.run(x)
        elif isinstance(obj, LTRect):
            obj.index = self.rect_index
            self.rect_index += 1
        elif isinstance(obj, LTCurve):
            obj.index = self.curve_index
            self.curve_index += 1
        elif isinstance(obj, LTImage):
            obj.index = self.image_index
            self.image_index += 1
        elif isinstance(obj, LTTextColumn):
            obj.index = self.column_index
            self.column_index += 1
        return


##  LAParams
##
class LAParams(object):
    def __init__(self,
                 line_overlap=0.5,
                 line_margin=0.5,
                 line_start_position_margin=3,
                 line_end_position_margin=10,
                 line_minimum_word_count=5,
                 line_maximum_spacing=0.6,

                 line_list_maximum_word_limit = 5,
                 char_margin=2.0,

                 char_margin_horizontal=0.1,
                 char_margin_vertical=0.3,
                 word_margin=0.1,
                 boxes_flow=0.5,
                 detect_vertical=False,
                 all_texts=False,
                 unmarked_list_word_count_margin = 1):
        self.line_overlap = line_overlap
        self.line_margin = line_margin
        self.line_start_position_margin = line_start_position_margin
        self.line_end_position_margin = line_end_position_margin
        self.line_minimum_word_count = line_minimum_word_count
        self.line_maximum_spacing = line_maximum_spacing
        self.line_list_maximum_word_limit = line_list_maximum_word_limit
        self.char_margin = char_margin
        self.char_margin_horizontal = char_margin_horizontal
        self.char_margin_vertical = char_margin_vertical
        self.word_margin = word_margin
        self.boxes_flow = boxes_flow
        self.detect_vertical = detect_vertical
        self.all_texts = all_texts
        self.closed_curves = {}
        self.closed_curve_index = 0
        self.unmarked_list_word_count_margin = unmarked_list_word_count_margin
        return

    def __repr__(self):
        return ('<LAParams: char_margin=%.1f, line_margin=%.1f, word_margin=%.1f all_texts=%r>' %
                (self.char_margin, self.line_margin, self.word_margin, self.all_texts))


##  LTItem
##
class LTItem(object):
    def analyze(self, laparams):
        """Perform the layout analysis."""
        return

##  LTGraphicObject
##
class LTGraphicObject(object):

    def __repr__(self):
        return ('<%s %r' %self.__class__.__name__, self.get_text())

    def get_text(self):
        raise NotImplementedError

##  LTText
##
class LTText(object):
    def __repr__(self):
        return ('<%s %r>' %
                (self.__class__.__name__, self.get_text()))

    def get_text(self):
        raise NotImplementedError


##  LTComponent
##
class LTComponent(LTItem):
    def __init__(self, bbox):
        LTItem.__init__(self)
        self.set_bbox(bbox)
        return

    def __repr__(self):
        return ('<%s %s>' %
                (self.__class__.__name__, bbox2str(self.bbox)))

    def set_bbox(self, (x0, y0, x1, y1)):
        self.x0 = int(x0)
        self.y0 = int(y0)
        self.x1 = int(x1)
        self.y1 = int(y1)
        self.width = x1 - x0
        self.height = y1 - y0
        self.bbox = (x0, y0, x1, y1)
        return

    def is_empty(self):
        return self.width <= 0 or self.height <= 0

    def is_hoverlap(self, obj):
        assert isinstance(obj, LTComponent)
        return int(obj.x0) <= int(self.x1) and int(self.x0) <= int(obj.x1)

    def hdistance(self, obj):
        assert isinstance(obj, LTComponent)
        if self.is_hoverlap(obj):
            return 0
        else:
            return min(abs(self.x0 - obj.x1), abs(self.x1 - obj.x0))

    def hoverlap(self, obj):
        assert isinstance(obj, LTComponent)
        if self.is_hoverlap(obj):
            return min(abs(self.x0 - obj.x1), abs(self.x1 - obj.x0))
        else:
            return 0

    def is_hoverlap_exacting(self, obj):
        if abs(obj.x0 - self.x1) <= 1 or abs(obj.x1 - self.x0) <= 1:
            if abs(obj.y0 - self.y0) <= 1 or abs(obj.y1 - self.y1) <= 1:
                return True
        return False

    def is_hoverlap_over_and_above(self, obj):
        if abs(obj.x0 - self.x1) >= 1 or abs(obj.x1 - self.x0) >= 1:
            if abs(obj.y0 - self.y0) >= 1 or abs(obj.y1 - self.y1) >= 1:
                return True
        return False

    def is_voverlap(self, obj):
        assert isinstance(obj, LTComponent)
        return obj.y0 <= self.y1 and self.y0 <= obj.y1

    def vdistance(self, obj):
        assert isinstance(obj, LTComponent)
        if self.is_voverlap(obj):
            return 0
        else:
            return min(abs(self.y0 - obj.y1), abs(self.y1 - obj.y0))

    def voverlap(self, obj):
        assert isinstance(obj, LTComponent)
        if self.is_voverlap(obj):
            return min(abs(self.y0 - obj.y1), abs(self.y1 - obj.y0))
        else:
            return 0

    def is_voverlap_exacting(self, obj):
        if abs(obj.y0 - self.y1) <= 1 or abs(obj.y1 - self.y0) <= 1:
            if abs(obj.x0 - self.x0) <= 1 or abs(obj.x1 - self.x1) <= 1:
                return True
        return False

    def is_voverlap_over_and_above(self, obj):
        if abs(obj.y0 - self.y1) >= 1 or abs(obj.y1 - self.y0) >= 1:
            if abs(obj.x0 - self.x0) >= 1 or abs(obj.x1 - self.x1) >= 1:
                return True
        return False

    def is_completely_contained(self, obj):
        if (self.x0 < obj.x0) and (self.x1 > obj.x1) and (self.y0 < obj.y0) and (self.y1 > obj.y1):
            return True
        else:
            return False


##  LTCurve
##
class LTCurve(LTComponent):
    def __init__(self, linewidth, pts, index=1):
        LTComponent.__init__(self, get_bound(pts))
        self.pts = pts
        self.linewidth = linewidth
        self.index = index
        return

    def get_pts(self):
        return ','.join('%.3f,%.3f' % p for p in self.pts)


##  LTLine
##
class LTLine(LTCurve):
    def __init__(self, linewidth, p0, p1, index = 1):
        LTCurve.__init__(self, linewidth, [p0, p1], index)
        return


##  LTRect
##
class LTRect(LTCurve):
    def __init__(self, linewidth, (x0, y0, x1, y1), index = 1):
        LTCurve.__init__(self, linewidth, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], index)
        return


##  LTImage
##
class LTImage(LTComponent):
    def __init__(self, name, stream, bbox):
        LTComponent.__init__(self, bbox)
        self.name = name
        self.stream = stream
        self.srcsize = (stream.get_any(('W', 'Width')),
                        stream.get_any(('H', 'Height')))
        self.imagemask = stream.get_any(('IM', 'ImageMask'))
        self.bits = stream.get_any(('BPC', 'BitsPerComponent'), 1)
        self.colorspace = stream.get_any(('CS', 'ColorSpace'))
        if not isinstance(self.colorspace, list):
            self.colorspace = [self.colorspace]
        return

    def __repr__(self):
        return ('<%s(%s) %s %r>' %
                (self.__class__.__name__, self.name,
                 bbox2str(self.bbox), self.srcsize))


##  LTAnno
##
class LTAnno(LTItem, LTText):
    def __init__(self, text):
        self._text = text
        return

    def get_text(self):
        return self._text


##  LTChar
##
class LTChar(LTComponent, LTText):
    def __init__(self, matrix, font, fontsize, fontcolor, scaling, rise,
                 text, textwidth, textdisp, textrotation=1):
        LTText.__init__(self)
        self._text = text
        self.matrix = matrix
        self.fontname = font.fontname
        self.fontcolor = fontcolor
        self.adv = textwidth * fontsize * scaling
        self.textrotation = textrotation
        # compute the boundary rectangle.
        if font.is_vertical():
            # vertical
            width = font.get_width() * fontsize
            (vx, vy) = textdisp
            if vx is None:
                vx = width // 2
            else:
                vx = vx * fontsize * .001
            vy = (1000 - vy) * fontsize * .001
            tx = -vx
            ty = vy + rise
            bll = (tx, ty + self.adv)
            bur = (tx + width, ty)
        else:
            # horizontal
            height = font.get_height() * fontsize
            descent = font.get_descent() * fontsize
            ty = descent + rise
            bll = (0, ty)
            bur = (self.adv, ty + height)
        (a, b, c, d, e, f) = self.matrix
        self.upright = (0 < a * d * scaling and b * c <= 0)
        if c == -b:
            if a != 0:
                textrotation = b / a, c / a, 0
            else:
                textrotation = 0, 0, 0
        else:
            if a != 0:
                textrotation = b / a, c / a, 0
            else:
                textrotation = 0, 0, 0
        self.textrotation = textrotation
        (x0, y0) = apply_matrix_pt(self.matrix, bll)
        (x1, y1) = apply_matrix_pt(self.matrix, bur)
        if x1 < x0:
            (x0, x1) = (x1, x0)
        if y1 < y0:
            (y0, y1) = (y1, y0)
        LTComponent.__init__(self, (x0, y0, x1, y1))
        if font.is_vertical():
            self.size = self.width
        else:
            #self.size = self.height
            if b == 0 and c == 0 and a != 1:
                self.size = a
            else:
                if a != 1:
                    self.size = sqrt(pow(a,2)+ pow(b,2))
                else:
                    self.size = self.height

            #if c != 0:
            #   self.size = self.size * c

        if self.fontcolor == '#ffffff':
            self.fontcolor = DEFAULT_TEXT_COLOR_BLACK

        if round(self.width) == 0:
            self.width = 1
            self.x1 = self.x1 + 1


        self.style = self.fontname + ":" + (self.fontcolor) + ":" + str(int(round(abs(self.size))))
        #print enc(self.get_text()),self
        return

    def __repr__(self):
        return ('<%s %s matrix=%s font=%r adv=%s text=%r>' %
                (self.__class__.__name__, bbox2str(self.bbox),
                 matrix2str(self.matrix), self.fontname, self.adv,
                 self.get_text()))

    def get_text(self):
        return self._text

    def is_compatible_horizontal(self, obj):
        """Returns True if two characters can coexist in the same line."""
        if (((obj.y0 + obj.y1) / 2 >= self.y0 and (obj.y0 + obj.y1) / 2 <= self.y1) and (
                            (self.y0 + self.y1) / 2 >= obj.y0 and (self.y0 + self.y1) / 2 <= obj.y1)) or (self.y0 < obj.y0 + (self.height/2) and self.y0 > obj.y0 - (self.height/2)):
            return True
        else:
            return False

    def is_compatible_vertical(self, obj):
        """Returns True if two characters can coexist in the same line."""
        #(Sridhar) Added height condtion as it was merging seperate paragraphs text
        if ((obj.x0 + obj.x1) / 2 > self.x0 and (obj.x0 + obj.x1) / 2 < self.x1) and (
                            (self.x0 + self.x1) / 2 > obj.x0 and (self.x0 + self.x1) / 2 < obj.x1) and (self.y1 + self.height <= obj.y0):
            return True
        else:
            return False


##  LTContainer
##
class LTContainer(LTComponent):
    def __init__(self, bbox):
        LTComponent.__init__(self, bbox)
        self._objs = []
        return

    def __iter__(self):
        return iter(self._objs)

    def __len__(self):
        return len(self._objs)

    def add(self, obj):
        self._objs.append(obj)
        return

    def sortthenadd(self, obj):
        index = len(self._objs) - 1
        if index < 0:
            self._objs.append(obj)
            return
        elif index == 0:
            self._objs.append(obj)
            if not self.comparator(self._objs[0], obj):
                self._objs[1] = self._objs[0]
                self._objs[0] = obj
                return
            else:
                self._objs.append(obj)
                return
        else:
            self._objs.append(obj)
            while index > 0 and not self.comparator(self._objs[index], obj):
                self._objs[index + 1] = self._objs[index]
                index -= 1
            self._objs[index + 1] = obj
        return

    def extend(self, objs):
        for obj in objs:
            self.add(obj)
        return

    def analyze(self, laparams):
        for obj in self._objs:
            obj.analyze(laparams)
        return

    def comparator(self, obj0, obj1):
        if obj1.y0 < obj0.y0:
            return True
        elif obj0.y0 == obj1.y0:
            if obj1.x0 >= obj0.x0:
                return True
        return False


##  LTExpandableContainer
##
class LTExpandableContainer(LTContainer):
    def __init__(self):
        LTContainer.__init__(self, (+INF, +INF, -INF, -INF))
        return

    def add(self, obj):
        if obj.x0 >= 0 and obj.x1 >= 0:
            LTContainer.add(self, obj)

            # """(Sridhar) Added this as vertical text word height is breaking textbox neighbour logic """
            # if isinstance(self,LTTextLineHorizontal) and isinstance(obj,LTTextWordVertical) and self._objs.__len__() > 1:
            #     self.set_bbox((min(self.x0, obj.x0),self.y0,
            #                max(self.x1, obj.x1),self.y1))
            # else:
            self.set_bbox((min(self.x0, obj.x0), min(self.y0, obj.y0),
                           max(self.x1, obj.x1), max(self.y1, obj.y1)))


        else:
            if not isinstance(obj, LTChar):
                LTContainer.add(self, obj)
                self.set_bbox((min(self.x0, obj.x0), min(self.y0, obj.y0),
                               max(self.x1, obj.x1), max(self.y1, obj.y1)))

        return


##  LTTextContainer
##
class LTTextContainer(LTExpandableContainer, LTText):
    def __init__(self):
        LTText.__init__(self)
        LTExpandableContainer.__init__(self)
        return

    def get_text(self):
        return ''.join(obj.get_text() for obj in self if isinstance(obj, LTText))


# LTTextWord
#
class LTTextWord(LTTextContainer):

    def __init__(self, char_margin, sentence_number = -1, text = "", char_space = 0 ):
        LTTextContainer.__init__(self)
        self.char_margin = char_margin
        self.sentence_number = sentence_number
        self.text = text
        self.char_space = char_space
        return

    def __repr__(self):
        return ('<%s %s %r>' % (self.__class__.__name__, bbox2str(self.bbox), self.get_text()))

    def get_text(self):
        return ''.join(obj.get_text() for obj in self if isinstance(obj, LTText))

    def get_style(self):
        obj = self._objs[0]
        return obj.get_style

    def get_rotation(self):
        obj = self._objs[0]
        return obj.textrotation

    def is_compatible_horizontal(self, obj):
        """Returns True if two words can coexist in the same line."""
        if (((obj.y0 + obj.y1) / 2 >= self.y0 and (obj.y0 + obj.y1) / 2 <= self.y1) and (
                            (self.y0 + self.y1) / 2 >= obj.y0 and (self.y0 + self.y1) / 2 <= obj.y1)):
            #or (self.y0 < obj.y0 + 4 and self.y0 > obj.y0 - 4) or (obj.y0 < self.y0 + 4 and obj.y0 > self.y0 - 4):
            return True
        else:
            return False

    def is_compatible_vertical(self, obj):
        """Returns True if two words can coexist in the same line."""
        if ((obj.x0 + obj.x1) / 2 > self.x0 and (obj.x0 + obj.x1) / 2 < self.x1) and (
                            (self.x0 + self.x1) / 2 > obj.x0 and (self.x0 + self.x1) / 2 < obj.x1) and (self.y1 + self.height <= obj.y0):
            return True
        else:
            return False

    def analyze(self, laparams):
        LTTextContainer.analyze(self, laparams)
        #self._objs = csort(self._objs, key = lambda obj: obj.x0)
        return

    def find_neighbours(self, plane, ratio):
        raise NotImplementedError


# LTTextWordHorizontal
#
class LTTextWordHorizontal(LTTextWord):

    def __init__(self, char_margin, sentence_number = -1, text = "", char_space = 0 ):
        LTTextWord.__init__(self, char_margin)
        self.char_margin = char_margin
        self._x1 = +INF
        self.char_space = char_space
        return

    def add(self, obj):
        if isinstance(obj, LTChar) and self.char_margin :
            margin = self.char_margin * obj.width

        if not obj.get_text().isspace():
            self._x1 = obj.x1
            if len(self._objs) == 1 :
                self.char_space = obj.x0 - self._objs[0].x1
            LTTextWord.add(self, obj)
        return

    def find_neighbours(self, plane, ratio):
        h = ratio * self.height
        objs = plane.find(self.x0 - h, self.y0 - h, self.x1 + h, self.y1 + h)
        return [obj for obj in objs if isinstance(obj, LTTextWordHorizontal)]


# LTTextWordVertical
#
class LTTextWordVertical(LTTextWord):

    def __init__(self, char_margin, sentence_number = -1, text = "", char_space = 0 ):
        LTTextWord.__init__(self, char_margin)
        self.char_margin = char_margin
        self._y0 = -INF
        self.char_space = char_space
        return

    def add(self, obj):
        if isinstance(obj, LTChar) and self.char_margin :
            margin = self.char_margin * obj.width

        if not obj.get_text().isspace():
            self._y0 = obj.y0
            textrotation = obj.textrotation
            xdeg = textrotation[0]
            ydeg = textrotation[1]
            obj.textrotation = (xdeg, ydeg, INF)
            LTTextWord.add(self, obj)
        return

    def find_neighbours(self, plane, ratio):
        w = ratio * self.height
        objs = plane.find(self.x0 - w, self.y0 - w, self.x1 + w, self.y1 + w)
        return [obj for obj in objs if isinstance(obj, LTTextWordVertical)]



##  LTTextLine
##
class LTTextLine(LTTextContainer):
    def __init__(self, word_margin, line_maximum_spacing, sparse = "normal line", checked=False):
        LTTextContainer.__init__(self)
        self.word_margin = word_margin
        self.line_maximum_spacing = line_maximum_spacing
        self.sparse = sparse
        self.checked = checked
        return

    def __repr__(self):
        return ('<%s %s %r>' %
                (self.__class__.__name__, bbox2str(self.bbox),
                 self.get_text()))

    def add(self, obj):
        LTTextContainer.add(self, obj)
        return

    def analyze(self, laparams):
        LTTextContainer.analyze(self, laparams)
        self._objs = csort(self._objs, key = lambda obj: obj.x0)
        #LTContainer.add(self, LTAnno('\n'))
        return

    def find_neighbors(self, plane, ratio):
        w = ratio * self.width
        objs = plane.find(self.x0 -w, self.yo. self.x1 + w, self.y1)
        return [ obj for obj in objs if isinstance(obj, LTTextLineVertical)]


class LTTextLineHorizontal(LTTextLine):
    def __init__(self, word_margin, line_maximum_spacing, sparse = "sparse line", nature = "normal" ):
        LTTextLine.__init__(self, word_margin, line_maximum_spacing)
        self._x1 = +INF
        self.sparse = sparse
        self.nature = nature
        return

    def add(self, obj):
        if isinstance(obj, LTChar) and self.word_margin:
            margin = self.word_margin * max(obj.width, obj.height)
            if self._x1 < obj.x0 - margin:
                LTContainer.add(self, LTAnno(' '))

        if bool(re.compile('[a-zA-Z]\.$|\(?[a-zA-Z].*\)').match(obj.get_text())):
            self.nature = LIST_LINE_LETTER_TYPE

        #print obj.get_text()
        if (obj.get_text() == '='):
            self.nature = "equation"
        self._x1 = obj.x1
        LTTextLine.add(self, obj)
        return

    def find_neighbors(self, plane, ratio):
        d = ratio * self.height
        objs = plane.find((self.x0, self.y0 - d, self.x1, self.y1 + d))

        return [obj for obj in objs
                if (isinstance(obj, LTTextLineHorizontal) and
                    abs(obj.height - self.height) < d and
                    (abs(obj.x0 - self.x0) < d or
                     abs(obj.x1 - self.x1) < d))]
    def isany(self,obj2,plane):
            """Check if there's any other object between obj1 and obj2.
            """
            x0 = min(self.x0, obj2.x0)
            y0 = min(self.y0, obj2.y0)
            x1 = max(self.x1, obj2.x1)
            y1 = max(self.y1, obj2.y1)
            objs = set(plane.find((x0, y0, x1, y1)))
            return objs.difference((self, obj2))


class LTTextLineVertical(LTTextLine):
    def __init__(self, word_margin, line_maximum_spacing, sparse = 'sparse line', nature = 'normal'):
        LTTextLine.__init__(self, word_margin, line_maximum_spacing)
        self.sparse = sparse
        self._y0 = -INF
        self.sparse = sparse
        self.nature = nature
        return

    def add(self, obj):
        if isinstance(obj, LTChar) and self.word_margin:
            margin = self.word_margin * max(obj.width, obj.height)
            if obj.y1 + margin < self._y0:
                LTContainer.add(self, LTAnno(' '))
        self._y0 = obj.y0
        LTTextLine.add(self, obj)
        return

    def find_neighbors(self, plane, ratio):
        d = ratio * self.width
        objs = plane.find((self.x0 - d, self.y0, self.x1 + d, self.y1))
        return [obj for obj in objs
                if (isinstance(obj, LTTextLineVertical) and
                    abs(obj.width - self.width) < d and
                    (abs(obj.y0 - self.y0) < d or
                     abs(obj.y1 - self.y1) < d))]


##  LTTextBox
##
##  A set of text objects that are grouped within
##  a certain rectangular area.
##
class LTTextBox(LTTextContainer):
    def __init__(self):
        LTTextContainer.__init__(self)
        self.index = -1
        self.sparse = "normal"
        self.sparsecount = 0
        self.type = 'body'
        self.is_hyphenation = False
        return

    def __repr__(self):
        return ('<%s(%s) %s %r>' %
                (self.__class__.__name__,
                 self.index, bbox2str(self.bbox), self.get_text()))

    def add(self, obj):
        LTContainer.add(self, obj)
        if obj.sparse == 'header line' :
            if len(self._objs) == 1 :
                self.type = 'heading'
        if (obj.nature == 'equation') and (len(obj._objs) > 3) :
            self.sparse = 'equation'
        self.set_bbox((min(self.x0, obj.x0), min(self.y0, obj.y0), max(self.x1, obj.x1), max(self.y1, obj.y1)))
        return

    #used for column generation
    def isany(self,obj1,obj2,plane):
            """Check if there's any other object between obj1 and obj2.
            """
            x0 = min(obj1.x0, obj2.x0)
            y0 = min(obj1.y0, obj2.y0)
            x1 = max(obj1.x1, obj2.x1)
            y1 = max(obj1.y1, obj2.y1)
            objs = set(self.find((x0, y0, x1, y1),obj2,plane))
            return objs.difference((obj1, obj2))

    #used for column generation
    def find(self, (x0, y0, x1, y1),obj2,plane):
        done = set()
        for k in plane._getrange((x0, y0, x1, y1)):
            if k not in plane._grid:
                continue
            for obj in plane._grid[k]:
                if obj in done or obj == self or obj == obj2:
                    continue
                done.add(obj)
                if ((obj.x0 <= x0 and obj.x1 <= x1 and obj.y0 >= y0 and obj.y1 <= y1) or (obj.x0 >= x0 and obj.x1 >= x1 and obj.y0 >= y0 and obj.y1 <= y1)or(obj.x0 >= x0 and obj.y0 >= y0 and obj.x1 <= x1 and obj.y1<= y1) or (obj.y0 < y0 and obj.y1 < y1 and obj.y1-1 > y0 and obj.x0 >= x0 and obj.x1 <= x1) or (obj.y0 > y0 and obj.y1 > y1 and obj.y0 < y1 and obj.x0 >= x0 and obj.x1 <= x1)):
                    yield obj
                else:
                    continue
        return


class LTTextBoxHorizontal(LTTextBox):
    def analyze(self, laparams):
        LTTextBox.analyze(self, laparams)
        self._objs = csort(self._objs, key=lambda obj: (-obj.y1,obj.x0))
        return

    def get_writing_mode(self):
        return 'lr-tb'

    def find_neighbors(self, plane, ratio):
        d = ratio * self.height
        objs = plane.find((self.x0, self.y0 - d, self.x1, self.y1 + d))

        return [obj for obj in objs
                if (isinstance(obj, LTTextBoxHorizontal) and
                     self.vdistance(obj) < (self._objs[0].height * 1.5 ))]

    def vdistance(self, obj):
        assert isinstance(obj, LTComponent)
        if self.y0 == obj.y0 and self.x0 == obj.x0:
            return 0;
        else:
            return min(abs(self._objs[0].y0 - obj._objs[-1].y1), abs(self._objs[0].y1 - obj._objs[-1].y0))


class LTTextBoxVertical(LTTextBox):
    def analyze(self, laparams):
        LTTextBox.analyze(self, laparams)
        self._objs = csort(self._objs, key=lambda obj: -obj.x1)
        return

    def get_writing_mode(self):
        return 'tb-rl'

#  LTTextColumn
##
##  A set of text objects that are grouped within
##  a certain column.
##

class LTTextColumn(LTTextContainer):
    def __init__(self):
        LTTextContainer.__init__(self)
        self.index = -1
        self.alignment = "left"
        return

    def __repr__(self):
        return ('<%s(%s) %s>' %
                (self.__class__.__name__,
                 self.index, bbox2str(self.bbox)))

    def add(self, obj):
        LTContainer.add(self, obj)
        self.set_bbox((min(self.x0, obj.x0), min(self.y0, obj.y0), max(self.x1, obj.x1), max(self.y1, obj.y1)))

        return


##  LTTextGroup
##
class LTTextGroup(LTTextContainer):
    def __init__(self, objs):
        LTTextContainer.__init__(self)
        self.extend(objs)
        return


class LTTextGroupLRTB(LTTextGroup):
    def analyze(self, laparams):
        LTTextGroup.analyze(self, laparams)
        #reorder the objects from top-left to bottom-right.
        self._objs = csort(self._objs, key=lambda obj:
        (1 - laparams.boxes_flow) * (obj.x0) -
        (1 + laparams.boxes_flow) * (obj.y0 + obj.y1))
        #self._objs.sort(key=lambda obj:(obj.x0,))
        return


class LTTextGroupTBRL(LTTextGroup):
    def analyze(self, laparams):
        LTTextGroup.analyze(self, laparams)
        # reorder the objects from top-right to bottom-left.
        self._objs = csort(self._objs, key=lambda obj:
        -(1 + laparams.boxes_flow) * (obj.x0 + obj.x1)
        - (1 - laparams.boxes_flow) * (obj.y1))
        return


class LTImageObjectContainer(LTExpandableContainer, LTImage):
    def __init__(self):
        LTGraphicObject.__init__(self)
        LTExpandableContainer.__init__(self)
        return


class LTImageBoxContainer(LTImageObjectContainer):
    def __init__(self):
        LTImageObjectContainer.__init__(self)
        return

    def __repr__(self):
        return ('<%s %s>' % self.__class__.__name__, bbox2str(self.bbox))

    def is_compatible(self, obj):
        raise NotImplementedError

    def analyze(self, laparams):
        LTImageObjectContainer.analyze(self, laparams)
        self._objs = csort(self._objs, key = lambda obj: obj.x0)
        return

##  LTLayoutContainer
##

class LTLayoutContainer(LTContainer):

    CentroidObject = namedtuple('CentroidObject', ['x', 'y'])

    def __init__(self, bbox, groups = None, image_boxes = None):
        LTContainer.__init__(self, bbox)
        self.groups = groups
        self.image_boxes = image_boxes
        return

    def get_image_boxes(self, laparams,  objs):
        obj0 = None

        for i in xrange(len(objs)):

            obj1 = objs[i]
            if obj1 is not None:
                for j in xrange(i+1, len(objs)):
                    obj2 = objs[j]
                    if obj2 is not None:
                        if obj1.is_voverlap_exacting(obj2) or obj1.is_hoverlap_exacting(obj2):
                            obj1.x0 = min(obj1.x0, obj2.x0)
                            obj1.x1 = max(obj1.x1, obj2.x1)
                            obj1.y0 = min(obj1.y0, obj2.y0)
                            obj1.y1 = max(obj1.y1, obj2.y1)
                            objs[j] = None

        for img in objs:
            if img is not None:
                imgbox = LTImageBoxContainer()
                imgbox.add(img)
                yield imgbox


        return

    def get_textlines(self, laparams, objs):
        obj0 = None
        line = None

        for obj1 in objs:
            if obj0 is not None:

                #print obj1," ",enc(obj1.get_text())
                #<LTTextWordHorizontal 111.00,173.00,138.00,184.00 u'Sauces'>   Sauces


                char_margin = laparams.char_margin

                if line is not None:

                    #print line.nature

                    if(line.nature == LIST_LINE_LETTER_TYPE):

                        char_margin = 0.75

                        #print 'found the merged options'

                k = 0
                #if obj1.y0 == 197 :
                #    print enc(obj1.get_text()),obj0
                #    print "hcompatible ",obj0.is_compatible_horizontal(obj1)
                #    print "vcompatible ",obj0.is_voverlap(obj1)
                #    print "heigh ",(min(obj0.height, obj1.height) * laparams.line_overlap) < obj0.voverlap(obj1)
                #    print "hdistance ",obj0.hdistance(obj1) < max(obj0.width, obj1.width) * char_margin
                #    print "over lap ",(obj0.y0 < obj1.y0 + 4 and obj0.y0 > obj1.y0 - 4)

                if ( obj0.is_compatible_horizontal(obj1) and obj0.is_voverlap(obj1) and (min(obj0.height, obj1.height) * laparams.line_overlap) < obj0.voverlap(obj1) and obj0.hdistance(obj1) < max(obj0.width, obj1.width) * char_margin):
                    k |= 1

                if (laparams.detect_vertical and obj0.is_compatible_vertical(obj1) and obj0.is_hoverlap(obj1) and (min(obj0.width, obj1.width) * laparams.line_overlap) < obj0.hoverlap(obj1) and obj0.vdistance(obj1) < min(obj0.height, obj1.height) * laparams.char_margin):
                    k |= 2

                if (k & 1 and isinstance(line, LTTextLineHorizontal)) or ( k & 2 and isinstance(line, LTTextLineVertical)):
                    line.add(obj1)

                elif line is not None:
                    yield line
                    line = None
                else:

                    if isinstance(obj0, LTTextWordVertical) and isinstance(obj1, LTTextWordVertical):
                        line = LTTextLineVertical(laparams.word_margin, laparams.line_maximum_spacing)
                        line.add(obj0)
                        line.add(obj1)

                    elif k == 1:
                        line = LTTextLineHorizontal(laparams.word_margin, laparams.line_maximum_spacing)
                        line.add(obj0)
                        line.add(obj1)

                    else:
                        line = LTTextLineHorizontal(laparams.word_margin,laparams.line_maximum_spacing)
                        line.add(obj0)
                        yield line
                        line = None
            obj0 = obj1

        if line is None:
            line = LTTextLineHorizontal(laparams.word_margin, laparams.line_maximum_spacing)
            line.add(obj0)
        yield line
        return


    def get_textwords(self, laparams, objs):


        obj0 = None
        word = None
        if len(objs) == 1:
            word = LTTextWordHorizontal(laparams.char_margin_horizontal)
            word.add(objs[0])
            yield word
            return
        for obj1 in objs:

            if obj0 is not None and not obj0.get_text().isspace():

                if word is not None:
                    if len(word._objs) == 0:
                        word = None
                k = 0
                word_split = False


                # if obj0.get_text() == ")" and obj1.get_text().isalpha():
                #
                #     if word is not None :
                #
                #
                #         yield word
                #         word = None
                #         word = LTTextWordHorizontal(laparams.char_margin_horizontal)
                #         word.add(obj1)
                #
                #
                #     else:
                #         word = LTTextWordHorizontal(laparams.char_margin_horizontal)
                #         word.add(obj0)
                #         yield word
                #         word = None
                #         word = LTTextWordHorizontal(laparams.char_margin_horizontal)
                #         word.add(obj1)
                # el
                #if obj1.x0 == 336 and obj1.y0 == 93:
                #print obj1,obj0
                #print "hcompatible ",obj0.is_compatible_horizontal(obj1)
                #print "vcompatible ",obj0.is_voverlap(obj1)
                #print "hdistance ",(min(obj0.height, obj1.height) * laparams.line_overlap) < obj0.voverlap(obj1)
                #print "over lap ",(obj0.y0 < obj1.y0 + (obj0.height/2) and obj0.y0 > obj1.y0 - (obj0.height/2))
                #print (obj0.y0+obj0.y1)/2, " ",obj0.height

                if word is not None:

                    if obj0.is_compatible_horizontal(obj1) and obj0.is_voverlap(obj1) and (obj0.hdistance(obj1) < max(obj0.width, obj1.width) * laparams.char_margin_horizontal):
                        k |= 1

                    if obj0.is_compatible_vertical(obj1) and obj0.is_hoverlap(obj1) and obj0.vdistance(obj1) < max(obj0.height, obj1.height) * laparams.char_margin_vertical:
                        k |= 2

                    if ((k & 1 and isinstance(word, LTTextWordHorizontal)) or (k & 2 and isinstance(word, LTTextWordVertical))):
                        if not obj1.get_text().isspace():
                            word.add(obj1)

                    elif word is not None and word.get_text():
                        if (obj0.is_compatible_horizontal(obj1) and obj0.is_voverlap(obj1) and obj0.hdistance(obj1)< max(obj0.width, obj1.width) * laparams.char_margin_horizontal and isinstance(word, LTTextWordHorizontal)) or (obj0.is_compatible_vertical(obj1) and obj0.is_hoverlap(obj1) and obj0.vdistance(obj1) < max(obj0.height, obj1.height) * laparams.char_margin_vertical and isinstance(word, LTTextWordVertical)):
                            word.add(obj1)
                        else:
                            if (isinstance(word, LTTextWordHorizontal) and (obj0.is_compatible_horizontal(obj1) and obj0.is_voverlap(obj1) and obj0.hdistance(obj1) < max(obj0.width, obj1.width) * laparams.char_margin_horizontal)):
                                yield word
                                word = None
                            elif (isinstance(word, LTTextWordVertical) and (obj0.is_compatible_vertical(obj1) and obj0.is_hoverlap(obj1) and obj0.vdistance(obj1) < max(obj0.height, obj1.height) * laparams.char_margin_vertical)):
                                yield word
                                word = None
                            else:
                                if len(word._objs) == 1 and obj0.is_compatible_vertical(obj1) and obj0.is_hoverlap(obj1) and obj0.vdistance(obj1) < max(obj0.height, obj1.height) * laparams.char_margin_vertical:
                                    word = None
                                    word = LTTextWordVertical(laparams.char_margin_vertical)
                                    word.add(obj0)
                                    word.add(obj1)
                                    word_split = True

                                else:
                                    yield word
                                    word = None

                            if not obj1.get_text().isspace() and not word_split:
                                if (obj0.is_compatible_horizontal(obj1) and obj0.is_voverlap(obj1) and obj0.hdistance(obj1) < max(obj0.width, obj1.width) * laparams.char_margin_horizontal):
                                    word = LTTextWordHorizontal(laparams.char_margin_horizontal)
                                    word.add(obj1)
                                elif (obj0.is_compatible_vertical(obj1) and obj0.is_hoverlap(obj1) and obj0.vdistance(obj1) < max(obj0.height, obj1.height) * laparams.char_margin_vertical):
                                    word = LTTextWordVertical(laparams.char_margin_vertical)
                                    word.add(obj1)
                                else:
                                    word = LTTextWordHorizontal(laparams.char_margin_horizontal)
                                    word.add(obj1)
                            else:
                                pass


                elif word is None:
                    if (obj0.is_compatible_horizontal(obj1) and obj0.is_voverlap(obj1) and obj0.hdistance(obj1)< max(obj0.width, obj1.width) * laparams.char_margin_horizontal) :
                        word = LTTextWordHorizontal(laparams.char_margin_horizontal)
                        if not obj0.get_text().isspace():
                            word.add(obj0)
                        if not obj1.get_text().isspace():
                            word.add(obj1)

                    elif (obj0.is_compatible_vertical(obj1) and obj0.is_hoverlap(obj1) and obj0.vdistance(obj1) < max(obj0.height, obj1.height) * laparams.char_margin_vertical):
                        word = LTTextWordVertical(laparams.char_margin_vertical)
                        if not obj0.get_text().isspace():
                            word.add(obj0)
                        if not obj1.get_text().isspace():
                            word.add(obj1)

                    else:
                        word = LTTextWordHorizontal(laparams.char_margin_horizontal)
                        if not obj0.get_text().isspace():
                            word.add(obj0)
                            yield word
                            word = None

                        word = LTTextWordHorizontal(laparams.char_margin_horizontal)
                        if not obj1.get_text().isspace():
                            word.add(obj1)
                        else:
                            pass

                else:
                    if not obj0.get_text().isspace():
                        word.add(obj0)
                    if not obj1.get_text().isspace():
                        word.add(obj1)
                    yield word

            if not obj1.get_text().isspace():
                obj0 = obj1
            else:
                if word is not None and word.get_text():
                    if len(word._objs) > 0:
                        yield word
                        word = None
                    else:
                        print 'illegal', word
                obj0 = obj1

        if not obj0.get_text().isspace() and word is None:
            word = LTTextWordHorizontal(laparams.char_margin_horizontal)
            word.add(obj0)

        if word is not None and word.get_text():
            yield word
            word = None

        return


    def get_textboxes(self, laparams, lines):

        plane = Plane(lines)
        boxes = {}
        previousline = None
        for line in lines:
            self.mark_the_line(lines, line, laparams)

        for line in lines:
            #if line.y0 == 98 and line.x0 == 346 :
            #    print "line ",line
            neighbors = line.find_neighbors(plane, laparams.line_margin)
            if(previousline is not None and line.y0 == previousline.y0):
                neighbors.append(previousline)
            members = []
            if len(neighbors) is not 0:
                members = [line]
                if len(neighbors) is not 0:

                    for obj1 in neighbors:
                        if self.check_paragraph(line, obj1, laparams):
                            members.append(obj1)
                            if obj1 in boxes:
                                members.extend(boxes.pop(obj1))

                    if isinstance(line, LTTextLineHorizontal):
                        box = LTTextBoxHorizontal()
                    else:
                        box = LTTextBoxVertical()
                    for obj in uniq(members):
                        box.add(obj)
                        boxes[obj] = box
                else:
                    box = LTTextBoxHorizontal()
                    box.add(obj)
                    boxes[obj] = box
            line.checked = True
            previousline =line

        done = set()
        try:
            for line in lines:
                #print "line",line
                try:
                    box = boxes[line]
                    if box in done: continue
                except:
                    pass
                done.add(box)
                box._objs.sort(key=lambda obj:(-obj.y0))


                if len(box._objs) == 1:
                    if(len(box._objs[0]._objs)>0):
                        yield box
                        continue

                yield box
                box = None
        except:
            print 'error in layout textbox grouping - line no. 945'
            pass

        return

    def get_textcolumns(self, laparams, textboxes):

        plane = Plane(textboxes)
        column = LTTextColumn()
        for textbox in textboxes:

            if textbox is not None:

                if len(column._objs) == 0:
                    column.add(textbox)
                else:
                    #print "textbox ",textbox,"last obj",column._objs[-1]
                    #print "isany ",textbox.isany(textbox,column._objs[-1],plane)
                    if ((textbox.x0 >= (column.x0 - 1)) and (textbox.x1 <= (column.x1 + 1))) or ((column.x0 >= (textbox.x0 -1)) and  (column.x1 <= (textbox.x1 + 1))) or ((column.y0 >= textbox._objs[0].y0) and (column.y1 >= textbox._objs[0].y1) and (column.x0 <= textbox._objs[0].x0)) or (not textbox.isany(textbox,column._objs[-1],plane)):
                        column.add(textbox)
                    else:
                        # print 'column splitted', column.y0, column.y1, textbox._objs[0].y0, textbox._objs[0].y1
                        yield column
                        column = LTTextColumn()
                        column.add(textbox)

        yield column
    #(Sridhar)Wrote new logic to find the columns so commented out if it works then remove this commented data
    def get_textcolumns_v2(self, laparams, textboxes,curveobjects):

         plane = Plane(textboxes)
         column_list=[]
         column = LTTextColumn()
         #for curve in curveobjects:
         #    print "cureve ",curve.y0

         for textbox in textboxes:
             if textbox is not None:
                 is_textbox_added = False

                 if len(column._objs) == 0:
                     column.add(textbox)
                 else:
                     #print "textbox ",textbox,"last obj",column._objs[-1]

                     if (((textbox.x0 >= (column.x0 - 1)) and (textbox.x1 <= (column.x1 + 1)) and (column.vdistance(textbox) < (textbox._objs[0].height*2)) ) or ((column.x0 >= (textbox.x0 -1)) and  (column.x1 <= (textbox.x1 + 1)) and (column.vdistance(textbox) < (textbox._objs[0].height*1.5))) ((column.y0 >= textbox._objs[0].y0) and (column.y1 >= textbox._objs[0].y1) and (column.x0 <= textbox._objs[0].x0)) or (not textbox.isany(textbox,column._objs[-1],plane))):
                         #print self.isAnyVectorInbetween(column,textbox,curveobjects)
                         column.add(textbox)

                         is_textbox_added=True
                     else:
                         for column_obj in column_list:
                             #print self.isAnyVectorInbetween(column_obj,textbox,curveobjects)
                             if (((textbox.x0 >= (column_obj.x0 - 1)) and (textbox.x1 <= (column_obj.x1 + 1)) and (column_obj.vdistance(textbox) < (textbox._objs[0].height*1.5))) or ((column_obj.x0 >= (textbox.x0 -1)) and  (column_obj.x1 <= (textbox.x1 + 1)) and (column_obj.vdistance(textbox) < (textbox.height*2)) and (column_obj.vdistance(textbox) < (textbox._objs[0].height*2))) ((column.y0 >= textbox._objs[0].y0) and (column.y1 >= textbox._objs[0].y1) and (column.x0 <= textbox._objs[0].x0)) or (not textbox.isany(textbox,column._objs[-1],plane))):
                                 column_obj.add(textbox)
                                 is_textbox_added=True
                             pass
                     if is_textbox_added is not True:
                         yield column
                         column_list.append(column)
                         column = LTTextColumn()
                         column.add(textbox)

         yield column
         column_list.append(column)

    """ added newly for testing by sridhar """
    def check_column(self, obj1, obj2,plane):

        if obj1 == obj2:
            return True
        #if obj1.isany(obj1,obj2, plane):
        #    return False
        if ((obj1.x0 >= (obj2.x0 - 1)) and (obj1.x1 <= (obj2.x1 + 1))) or ((obj2.x0 >= (obj1.x0 -1)) and  (obj2.x1 <= (obj1.x1 + 1))) or ((obj1.x0 >= obj2.x0) and (obj1.x1 >= obj2.x1)):
            return True
        #if ((obj1.x0 >= (obj2.x0 - 1)) and (obj1.x1 <= (obj2.x1 + 1)) and (obj2.vdistance(obj1) < (obj1._objs[0].height * 1.5 )) ) or ((obj2.x0 >= (obj1.x0 -1)) and  (obj2.x1 <= (obj1.x1 + 1)) and (obj2.vdistance(obj1) < (obj1._objs[0].height * 1.5 ))):# or ((column.y0 >= textbox._objs[0].y0) and (column.y1 >= textbox._objs[0].y1) and (column.x0 <= textbox._objs[0].x0)):

        return False

    def check_paragraph(self, obj1, obj2, laparams):

        if obj1 == obj2:
            return True

        if obj1.y0 == obj2.y0:
            return True


        if obj1.sparse != obj2.sparse :
            return False
        if obj1.y0 > obj2.y0 and  obj2.checked is not True:
            if self.check_para(obj1, obj2, laparams):
                return True
            else:
                return False
        elif obj2.checked is True:
            if self.check_para(obj2, obj1, laparams):
                return True
            else:
                return False
        return True

    def check_para(self, obj1, obj2, laparams):


        if self.check_list(obj2, laparams) and self.check_list(obj1, laparams):
            return False


        # if (self.check_first_character(obj1) and self.check_first_character(obj2) \
        #              and bool(re.compile('.+[a-zA-Z,]$').match(obj1._objs[-1].get_text())) \
        #              and bool(re.compile('.+[a-zA-Z,]$').match(obj2._objs[-1].get_text())) \
        #              and len(obj1._objs) < laparams.line_list_maximum_word_limit ) or (len(obj1._objs) < laparams.line_list_maximum_word_limit and bool(re.compile('^[A-Z0-9]').match(obj1._objs[-1].get_text())) and bool(re.compile('^[A-Z0-9]').match(obj2._objs[-1].get_text()))):
        #
        #     if not bool(re.compile('((^[\(a-zA-Z0-9]{0,3}[.]+$))').match(obj1._objs[0].get_text())):
        #         obj1.sparse = LIST_LINE_UNMARKED_TYPE
        #     if not bool(re.compile('((^[a-zA-Z0-9]{0,3}[.]+$))').match(obj2._objs[0].get_text())):
        #         obj2.sparse = LIST_LINE_UNMARKED_TYPE
        #     return True

        if (self.check_first_character(obj1) and self.check_first_character(obj2) \
                    and bool(re.compile('.+[a-zA-Z,]$').match(obj1._objs[-1].get_text())) \
                    and bool(re.compile('.+[a-zA-Z,]$').match(obj2._objs[-1].get_text())) \
                    and len(obj1._objs) < laparams.line_list_maximum_word_limit ) or (len(obj1._objs) < laparams.line_list_maximum_word_limit and bool(re.compile('^[A-Z0-9]').match(obj1._objs[-1].get_text())) and bool(re.compile('^[A-Z0-9]').match(obj2._objs[-1].get_text()))):

            if not bool(re.compile('((^[\(a-zA-Z0-9]{0,3}[.]+$))').match(obj1._objs[0].get_text())):
                obj1.sparse = LIST_LINE_UNMARKED_TYPE
            if not bool(re.compile('((^[a-zA-Z0-9]{0,3}[.]+$))').match(obj2._objs[0].get_text())):
                obj2.sparse = LIST_LINE_UNMARKED_TYPE
            return True


        if int(obj1.height) != int(obj2.height) and not(obj1.sparse is NORMAL_LINE and obj2.sparse is NORMAL_LINE):
            return True

        # if bool(re.compile('.+[^a-zA-Z0-9,]$').match(obj1._objs[-1].get_text())) and self.check_first_character(obj2):
        #     if obj1.x0 - obj2.x0 >= laparams.line_start_position_margin or abs(obj1.x1 - obj2.x1) >= laparams.line_end_position_margin \
        #             :
        #
        #         return True


        return True


    def check_list(self, obj, laparams):

        is_list_numeral_type = bool(re.compile('\d{1,5}[\.\-]|\(\d{1,5}[\.\-]*\)').match(obj._objs[0].get_text()))
        is_list_letter_type =  bool(re.compile('[a-zA-Z]{1,3}\.$|\(?[a-zA-Z].*\)').match(obj._objs[0].get_text()))
        is_list_symbol_type =  bool(re.compile('\u2022').match(obj._objs[0].get_text()))

        # is_list_unmarked_type = bool(len(obj._objs) < laparams.line_list_maximum_word_limit and bool(re.compile('^[A-Z0-9]').match(obj._objs[-1].get_text())))

        is_list_unmarked_type = bool((len(obj._objs)<=laparams.line_list_maximum_word_limit) and self.check_unmarkedlist(obj,laparams))

        is_list_parenthesis_type = False


     #   if is_list_letter_type:
      #      if len(obj._objs[0].get_text()) >= 6:
       #         is_list_parenthesis_type = True

        if is_list_numeral_type:
            obj.sparse = LIST_LINE_NUMERAL_TYPE
            return True
        elif is_list_letter_type:

            if is_list_parenthesis_type:
                obj.sparse = LIST_LINE_PARENTHESIS_TYPE
            else:
                obj.sparse = LIST_LINE_LETTER_TYPE
            return True
        elif is_list_symbol_type:
            obj.sparse = LIST_LINE_SYMBOL_TYPE
            return True
        # elif is_list_unmarked_type:
        #     obj.sparse = LIST_LINE_UNMARKED_TYPE
        #     return True
        return False


    def check_unmarkedlist(self,line, laparams):
        word_with_caps_begin_count = 0
        for word in line:
            if re.compile('^[A-Z0-9]').match(word.get_text()):
                word_with_caps_begin_count += 1
        line_length = len(line._objs)

        if line_length > 2:
            if(line_length - word_with_caps_begin_count <= laparams.unmarked_list_word_count_margin):
                return True
            else:
                return False
        else:
            if line_length == word_with_caps_begin_count:
                if len(line._objs) == 1 and len(line._objs[0]._objs) == 1:
                    return False
                else:
                    return True
            else:
                return False
        return True


    def check_first_character(self, obj):
        if len(obj._objs[0]._objs) > 1:
            if obj._objs[0]._objs[0].get_text().isupper() or obj._objs[0]._objs[1].get_text().isupper():
                return True
            else:
                return False
        elif obj._objs[0]._objs[0].get_text().isupper():
            return True
        return False

    def mark_the_line(self, lines, obj, laparams):

        if len(obj.get_text()) == 0 or len(obj._objs[0].get_text()) == 0:
            lines.remove(obj)
            return
        if obj.width != 0:
            first_word_text =obj._objs[0].get_text()
            if self.check_list(obj, laparams):
                return
           # elif (self.get_character_area(obj)/(obj.width * 1.0) < laparams.line_maximum_spacing):
            #    obj.sparse = TABLE_LINE

            else:
                obj.sparse = NORMAL_LINE
        return


    def get_character_area(self, obj):
        total_area = 0
        for obj in obj._objs:
            total_area += obj.width
        return total_area







    # group_objects: group text object to textlines.
    def group_objects(self, laparams, objs):
        obj0 = None
        line = None
        for obj1 in objs:
            if obj0 is not None:
                # halign: obj0 and obj1 is horizontally aligned.
                #
                #   +------+ - - -
                #   | obj0 | - - +------+   -
                #   |      |     | obj1 |   | (line_overlap)
                #   +------+ - - |      |   -
                #          - - - +------+
                #
                #          |<--->|
                #        (char_margin)
                halign = (obj0.is_compatible(obj1) and
                          obj0.is_voverlap(obj1) and
                          (min(obj0.height, obj1.height) * laparams.line_overlap <
                           obj0.voverlap(obj1)) and
                          (obj0.hdistance(obj1) <
                           max(obj0.width, obj1.width) * laparams.char_margin))

                # valign: obj0 and obj1 is vertically aligned.
                #
                #   +------+
                #   | obj0 |
                #   |      |
                #   +------+ - - -
                #     |    |     | (char_margin)
                #     +------+ - -
                #     | obj1 |
                #     |      |
                #     +------+
                #
                #     |<-->|
                #   (line_overlap)
                valign = (laparams.detect_vertical and
                          obj0.is_compatible(obj1) and
                          obj0.is_hoverlap(obj1) and
                          (min(obj0.width, obj1.width) * laparams.line_overlap <
                           obj0.hoverlap(obj1)) and
                          (obj0.vdistance(obj1) <
                           max(obj0.height, obj1.height) * laparams.char_margin))

                if ((halign and isinstance(line, LTTextLineHorizontal)) or
                        (valign and isinstance(line, LTTextLineVertical))):
                    line.add(obj1)
                elif line is not None:
                    yield line
                    line = None
                else:
                    if valign and not halign:
                        line = LTTextLineVertical(laparams.word_margin)
                        line.add(obj0)
                        line.add(obj1)
                    elif halign and not valign:
                        line = LTTextLineHorizontal(laparams.word_margin)
                        line.add(obj0)
                        line.add(obj1)
                    else:
                        line = LTTextLineHorizontal(laparams.word_margin)
                        line.add(obj0)
                        yield line
                        line = None
            obj0 = obj1
        if line is None:
            line = LTTextLineHorizontal(laparams.word_margin)
            line.add(obj0)
        yield line
        return

    # group_textlines: group neighboring lines to textboxes.
    def group_textlines(self, laparams, lines):
        plane = Plane(self.bbox)
        plane.extend(lines)
        boxes = {}
        for line in lines:
            neighbors = line.find_neighbors(plane, laparams.line_margin)
            if line not in neighbors: continue
            members = []
            for obj1 in neighbors:
                members.append(obj1)
                if obj1 in boxes:
                    members.extend(boxes.pop(obj1))
            if isinstance(line, LTTextLineHorizontal):
                box = LTTextBoxHorizontal()
            else:
                box = LTTextBoxVertical()
            for obj in uniq(members):
                box.add(obj)
                boxes[obj] = box
        done = set()
        for line in lines:
            if line not in boxes: continue
            box = boxes[line]
            if box in done:
                continue
            done.add(box)
            if not box.is_empty():
                if len(box._objs) == 1:
                    if(len(box._objs[0]._objs)>0):
                         yield box
                         continue
                yield box
        return

    # group_textboxes: group textboxes hierarchically.
    def group_textboxes(self, laparams, boxes):
        assert boxes

        #print self.is_formula_page
        #if self.is_formula_page:
        #    return
        def dist(obj1, obj2):
            """A distance function between two TextBoxes.

            Consider the bounding rectangle for obj1 and obj2.
            Return its area less the areas of obj1 and obj2,
            shown as 'www' below. This value may be negative.
                    +------+..........+ (x1, y1)
                    | obj1 |wwwwwwwwww:
                    +------+www+------+
                    :wwwwwwwwww| obj2 |
            (x0, y0) +..........+------+
            """
            x0 = min(obj1.x0, obj2.x0)
            y0 = min(obj1.y0, obj2.y0)
            x1 = max(obj1.x1, obj2.x1)
            y1 = max(obj1.y1, obj2.y1)
            return ((x1 - x0) * (y1 - y0) - obj1.width * obj1.height - obj2.width * obj2.height)

        def isany(obj1, obj2):
            """Check if there's any other object between obj1 and obj2.
            """
            x0 = min(obj1.x0, obj2.x0)
            y0 = min(obj1.y0, obj2.y0)
            x1 = max(obj1.x1, obj2.x1)
            y1 = max(obj1.y1, obj2.y1)
            objs = set(plane.find((x0, y0, x1, y1)))
            return objs.difference((obj1, obj2))

        # XXX this still takes O(n^2)  :(
        for box in boxes:
            if box is None:
                boxes.remove(box)
        dists = []
        for i in xrange(len(boxes)):
            obj1 = boxes[i]
            for j in xrange(i+1, len(boxes)):
                obj2 = boxes[j]
                if obj1 is not None and obj2 is not None:
                    dists.append((0, dist(obj1, obj2), obj1, obj2))
        dists.sort()
        plane = Plane(boxes)
        #plane.extend(boxes)
        while dists:
            (c, d, obj1, obj2) = dists.pop(0)
            if c == 0 and isany(obj1, obj2):
                dists.append((1, d, obj1, obj2))
                continue
            if (isinstance(obj1, LTTextBoxVertical) or
                    isinstance(obj1, LTTextGroupTBRL) or
                    isinstance(obj2, LTTextBoxVertical) or
                    isinstance(obj2, LTTextGroupTBRL)):
                group = LTTextGroupTBRL([obj1, obj2])
            else:
                group = LTTextGroupLRTB([obj1, obj2])

            if obj1 in plane:
                plane.remove(obj1)
            if obj2 in plane:
                plane.remove(obj2)
            # this line is optimized -- don't change without profiling
            dists = [n for n in dists if n[2] in plane._objs and n[3] in plane._objs]
            for other in plane:
                dists.append((0, dist(group, other), group, other))
            dists.sort()
            plane.add(group)
        len(plane) == 1
        return list(plane)

    def remove_hidden_items(self):
        for obj in self._objs:
            state = False
            if isinstance(obj, LTChar):
                if len(obj.get_text()) == 0:
                    self._objs.remove(obj)
            elif not isinstance(obj, LTCurve):
                for x in range(int(obj.x0) + 1, int(obj.x1) - 1):
                    for y in range(int(obj.y0), int(obj.y1)):
                        if (x,y) in object_dictionary:
                            if object_dictionary[(x,y)] in self._objs and isinstance(object_dictionary[(x,y)], LTChar) and not isinstance(obj, LTCurve):
                                index = self._objs.index(object_dictionary[(x,y)])
                                self._objs.remove((object_dictionary[x,y]))
                                state = True

                x_mid = int(obj.x0 + obj.x1)/2
                y_mid = int(obj.y0 + obj.y1)/2
                object_dictionary[(x_mid,y_mid)] = obj
        return

    @classmethod
    def get_the_distance(cls, x0, y0, x1, y1):
        try:
            return math.sqrt(math.pow(y1 - y0, 2) + math.pow(x1 - x0, 2))
        except Exception, e:
            print e

    @classmethod
    def get_the_centroid(cls, box):
        try:
            print type(box.x0)
            centroid_x = (box.x1 - box.x0) / 2
            centroid_y = (box.y1 - box.y0) / 2
            return centroid_x, centroid_y
        except Exception, e:
            print e

    @classmethod
    def get_the_minimum_three_distances_from_image_to_para(cls, imageboxes, textboxes):
        try:
            # print 'hi'
            # print imageboxes
            result_imageboxes = []
            for imagebox in imageboxes:
                distance_list = []
                # print 'imagebox ', imagebox
                centroid_image_x, centroid_image_y = LTLayoutContainer.get_the_centroid(imagebox)
                # print 'type ', type(centroid_image_x)
                for textbox in textboxes:
                    centroid_textbox_x, centroid_textbox_y = LTLayoutContainer.get_the_centroid(textbox)
                    distance_btn_centroid = LTLayoutContainer.get_the_distance(centroid_image_x, centroid_image_y,
                                                                               centroid_textbox_x, centroid_textbox_y)
                    # print 'distance betwween centroid ', distance_btn_centroid
                    distance_list.append((distance_btn_centroid, textbox.index))
                # print distance_list.sort()
                imagebox.minimum_distance_to_para = distance_list[:3]
                # print 'imagebox 1 ', imagebox
                result_imageboxes.append(imagebox)
            return imageboxes
        except Exception, e:
            # print 'bye'
            print e


    def analyze(self, laparams):

        (imageobjects, textallobjects) = fsplit(lambda obj: isinstance(obj, LTFigure), self._objs)
        print 'image objects ', imageobjects
        imageboxes = list(self.get_image_boxes(laparams, imageobjects))

        (curveobjects, otherobjects) = fsplit(lambda obj: isinstance(obj, LTCurve), self._objs)
        print 'curve objects ', curveobjects
        # textobjs is a list of LTChar objects, i.e.
        # it has all the individual characters in the page.
        (textobjects, otherobjects) = fsplit(lambda  obj: isinstance(obj, LTChar), self._objs)

        #(Sridhar) Added to escape space character
        for textobj in textobjects:
            if textobj is not None and len(textobj.get_text()) == 1 and (ord(textobj.get_text())==160):
                textobj._text=unichr(58863)


        for obj in otherobjects:
            obj.analyze(laparams)

        if len(textobjects) == 0:
            print 'Layout.py (analyze method) line no. 1246: Returning without doing anything since no characters were found'
            return

        words =list(self.get_textwords(laparams,textobjects))
        #print 'words found',words
        if not words:
            print 'Layout.py (analyze method) line no. 1250: Returning without doing anything since no words were found'
            return
        for obj in words:
            #print enc(obj.get_text()),obj
            obj.analyze(laparams)
        textlines = list(self.get_textlines(laparams, words))
        #textlines.sort(key=lambda obj:(-obj.y0,obj.x0))
        #print textlines
        #print 'lines found'



        for line in textlines:
            #print "textline ",line,"\n"
            if len(line._objs) == 0:
                if line in self._objs:

                    self._objs.remove(obj)
        if len(textlines) == 0:
            return
        for obj in textlines:
            obj.analyze(laparams)
        textboxes = list(self.get_textboxes(laparams, textlines))

        #print textboxes
        if not textboxes:
            print 'Layout.py (analyze method) line no. 1265: Returning without doing anything since no textboxes were found'
            return


        groups = self.group_textboxes(laparams, textboxes)




        #groups = self.group_textboxes(laparams, textboxes)

        groups = []


        #print 'groups found', groups
        assigner = IndexAssigner()

        #if not self.is_formula_page:
        #for group in groups:
        #   group.analyze(laparams)
        #  assigner.run(group)
        #else:
        #LTTextGroup.analyze(self, laparams)




        """paragraph ID Generation"""
        for textbox in textboxes:
            textbox.analyze(laparams)
            assigner.run(textbox)


        for otherobject in otherobjects:
            assigner.run(otherobject)

        for curve in curveobjects:
            assigner.run(curve)

        for image in imageobjects:
            assigner.run(image)
        # textboxes.sort(key=lambda box: box.index)

        # textboxes = [x for x in textboxes if x is not None]
        #
        # textboxes.sort(key=lambda box: box.index)

        #for obj in textboxes:
        #    print enc(obj.get_text())," box ",obj

        #print textboxes
        if curveobjects:
            curveobjects = LTLayoutContainer.get_the_minimum_three_distances_from_image_to_para(curveobjects, textboxes)

        if imageobjects:
            imageobjects = LTLayoutContainer.get_the_minimum_three_distances_from_image_to_para(imageobjects, textboxes)

        columns = list(self.get_textcolumns(laparams, textboxes))
        #columns = list(self.get_textcolumns_v2(laparams, textboxes,curveobjects))

        column_groups = self.group_textcolumns(laparams,columns)

        column_assigner = IndexAssigner()

        for column in columns:
            column_assigner.run(column)

         #if not self.is_formula_page:
        for column_group in column_groups:
            column_group.analyze(laparams)
            column_assigner.run(column_group)



        self._objs = column_groups  + imageobjects + curveobjects

        self.groups = groups + column_groups




        self.image_boxes = imageobjects
        return




##  LTFigure
##
class LTFigure(LTLayoutContainer):
    def __init__(self, name, bbox, matrix):
        self.name = name
        self.matrix = matrix
        (x, y, w, h) = bbox
        bbox = get_bound(apply_matrix_pt(matrix, (p, q))
                         for (p, q) in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)))
        LTLayoutContainer.__init__(self, bbox)
        return

    def __repr__(self):
        return ('<%s(%s) %s matrix=%s>' %
                (self.__class__.__name__, self.name,
                 bbox2str(self.bbox), matrix2str(self.matrix)))

    def analyze(self, laparams):
        if not laparams.all_texts:
            return
        LTLayoutContainer.analyze(self, laparams)
        return


##  LTPage
##
class LTPage(LTLayoutContainer):
    def __init__(self, pageid, bbox, rotate=0):
        LTLayoutContainer.__init__(self, bbox)
        self.pageid = pageid
        self.rotate = rotate
        return

    def __repr__(self):
        return ('<%s(%r) %s rotate=%r>' %
                (self.__class__.__name__, self.pageid,
                 bbox2str(self.bbox)
                 , self.rotate))


# group_textcolumns: group textcolumns hierarchically.

    def group_textcolumns(self, laparams, columns):
        assert columns

        #print self.is_formula_page
        #if self.is_formula_page:
        #    return
        def dist(obj1, obj2):
            """A distance function between two TextBoxes.

            Consider the bounding rectangle for obj1 and obj2.
            Return its area less the areas of obj1 and obj2,
            shown as 'www' below. This value may be negative.
                    +------+..........+ (x1, y1)
                    | obj1 |wwwwwwwwww:
                    +------+www+------+
                    :wwwwwwwwww| obj2 |
            (x0, y0) +..........+------+
            """
            x0 = min(obj1.x0, obj2.x0)
            y0 = min(obj1.y0, obj2.y0)
            x1 = max(obj1.x1, obj2.x1)
            y1 = max(obj1.y1, obj2.y1)
            return ((x1 - x0) * (y1 - y0) - obj1.width * obj1.height - obj2.width * obj2.height)

        def isany(obj1, obj2):
            """Check if there's any other object between obj1 and obj2.
            """
            x0 = min(obj1.x0, obj2.x0)
            y0 = min(obj1.y0, obj2.y0)
            x1 = max(obj1.x1, obj2.x1)
            y1 = max(obj1.y1, obj2.y1)
            objs = set(plane.find((x0, y0, x1, y1)))
            return objs.difference((obj1, obj2))

        # XXX this still takes O(n^2)  :(
        for column in columns:
            if column is None:
                columns.remove(column)
        dists = []
        for i in xrange(len(columns)):
            obj1 = columns[i]
            for j in xrange(i+1, len(columns)):
                obj2 = columns[j]
                if obj1 is not None and obj2 is not None:
                    dists.append((0, dist(obj1, obj2), obj1, obj2))
        dists.sort()
        plane = Plane(columns)
        #plane.extend(boxes)
        while dists:
            (c, d, obj1, obj2) = dists.pop(0)
            if c == 0 and isany(obj1, obj2):
                dists.append((1, d, obj1, obj2))
                continue
            if (isinstance(obj1, LTTextBoxVertical) or
                    isinstance(obj1, LTTextColumnTBRL) or
                    isinstance(obj2, LTTextBoxVertical) or
                    isinstance(obj2, LTTextColumnTBRL)):
                group = LTTextColumnTBRL([obj1, obj2])
            else:
                group = LTTextColumnLRTB([obj1, obj2])

            if obj1 in plane:
                plane.remove(obj1)
            if obj2 in plane:
                plane.remove(obj2)
            # this line is optimized -- don't change without profiling
            dists = [n for n in dists if n[2] in plane._objs and n[3] in plane._objs]
            for other in plane:
                dists.append((0, dist(group, other), group, other))
            dists.sort()
            plane.add(group)
        len(plane) == 1
        return list(plane)



##  LTTextColumnGroup
##
class LTTextColumnGroup(LTTextContainer):
    def __init__(self, objs):
        LTTextContainer.__init__(self)
        self.extend(objs)
        return


class LTTextColumnLRTB(LTTextColumnGroup):
    def analyze(self, laparams):
        LTTextColumnGroup.analyze(self, laparams)
        # reorder the objects from top-left to bottom-right.
        self._objs = csort(self._objs, key=lambda obj:
        (1 - laparams.boxes_flow) * (obj.x0) -
        (1 + laparams.boxes_flow) * (obj.y0 + obj.y1))
        return


class LTTextColumnTBRL(LTTextColumnGroup):
    def analyze(self, laparams):
        LTTextColumnGroup.analyze(self, laparams)
        # reorder the objects from top-right to bottom-left.
        self._objs = csort(self._objs, key=lambda obj:
        -(1 + laparams.boxes_flow) * (obj.x0 + obj.x1)
        - (1 - laparams.boxes_flow) * (obj.y1))
        return