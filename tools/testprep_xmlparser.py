from collections import deque
import sys
import linecache
import re
import os
import codecs
from os import walk
from bs4 import BeautifulSoup as bs

#predifined tags
XML_TAGS = {
    'PAGES': 'pages',
    'PAGE': 'page',
    'TEXTCOLUMN': 'textcolumn',
    'TEXTPARA': 'textpara',
    'TEXTLINE': 'textline',
    'TEXTWORD': 'textword',

}

TEST_SECTION_TITLE_REGULAR_EXPRESSION = '^Exercise\d+'
TEST_QUESTION_REGULAR_EXPRESSION = ur'(^\d*[\.\-])(.*$)'
ANSWER_SET_TITLE = ur'Answers with Explanation'
ANSWER_KEY_REGULAR_EXPRESSION = ur'(^\d*[\.\-])\s*\(?[A,B,C,D,E,a,b,c,d,e]\)'
TEST_QUESTION_REGULAR_EXPRESSION_COMPILED = re.compile(TEST_QUESTION_REGULAR_EXPRESSION)
TEST_QUESTION_ANSWER_KEY_MATCHING_EXPRESSION = "[0-9]+\\."
QUESTION_NUMBER_IN_QSD_EXPRESSION = "[0-9]+"
TEST_OPTION_REGULAR_EXPRESSION = ur'^\(?[A,B,C,D,E,a,b,c,d,e]\)'
TEST_OPTION_REGULAR_EXPRESSION_COMPILED = re.compile(TEST_OPTION_REGULAR_EXPRESSION)
QUESTION_SET_REGULAR_EXPRESSION = '^Directions(.*)'

FirstOptionCharArr = ['(A)', 'A)']
SecondOptionCharArr = ['(B)', 'B)']
ThirdOptionCharArr = ['(C)', 'C)']
FourthOptionCharArr = ['(D)', 'D)']
FifthOptionCharArr = ['(E)', 'E)']

# TAGS
PAGES_TAG = 'pages'
PAGE_TAG = 'page'
TEXTCOLUMN_TAG = 'textcolumn'
TEXTPARA_TAG = 'textpara'
TEXTLINE_TAG = 'textline'
TEXTWORD_TAG = 'textword'
TEXT_TAG = 'text'

QUESTION_TAG = '<Question>'
QUESTION_DESCRIPTION_TAG = ''


def parse_word_text(word_tag):
    text_tag = word_tag.find(TEXT_TAG)
    if text_tag:
        return text_tag.text


def parse_line_text(line_tag):
    word_tags = line_tag.find_all(TEXTWORD_TAG)
    string = ''
    for word_tag in word_tags:
        #print word_tag
        string += parse_word_text(word_tag)
    return string


def parse_para_text(para_tag):
    line_tags = para_tag.find_all(TEXTLINE_TAG)
    string = ''
    for line_tag in line_tags:
        string += parse_line_text(line_tag)
    return string


# def get_the_full_answer_key(index, para_tags):
#     new_para_tags = para_tags[index:]
#     string = ''
#     for i, para_tag in enumerate(new_para_tags):
#         # print para_tag
#         parsed_para_text = parse_para_text(para_tag)
#         parsed_para = parse_para(para_tag)
#         result_option = re.search(ANSWER_KEY_REGULAR_EXPRESSION, parsed_para_text)
#         if result_option and i != 0:
#             break
#         string += parsed_para
#     # print string
#     return string
def get_the_section_title(index, textline_tags):
    new_textline_tags = textline_tags[index:]
    soup = bs()
    section_title_tag = soup.new_tag('SectionTitle')
    for section_title_index, line_tag in enumerate(new_textline_tags):
        textline_text = parse_line_text(line_tag)
        result_question = re.search(TEST_QUESTION_REGULAR_EXPRESSION_COMPILED, textline_text)
        result_question_set = re.search(QUESTION_SET_REGULAR_EXPRESSION, textline_text)
        if result_question or result_question_set:
            break
        # section_title_tag.append(line_tag)
        section_title_tag.append(textline_text)
    # print section_title_index + index
    print section_title_tag
    return section_title_index + index, section_title_tag


def get_the_complete_question_set_description(index, textline_tags):
    new_textline_tags = textline_tags[index:]
    soup = bs()
    question_set_description_tag = soup.new_tag('QuestionSetDescription')
    xwidth_line_tag = []
    yheight_line_tag = []
    for question_set_description_index, line_tag in enumerate(new_textline_tags):
        if question_set_description_index == 0:
            x0, width = float(line_tag['x']), float(line_tag['width'])
            y0, height = float(line_tag['y']), float(line_tag['height'])
        textline_text = parse_line_text(line_tag)
        result_question = re.search(TEST_QUESTION_REGULAR_EXPRESSION_COMPILED, textline_text)
        if result_question:
            break
        yheight_line_tag.append((float(line_tag['y']), float(line_tag['height'])))
        xwidth_line_tag.append((float(line_tag['x']), float(line_tag['width'])))
        # question_set_description_tag.append(line_tag)
        question_set_description_tag.append(textline_text)
    max_x0, max_width = max(xwidth_line_tag)
    max_y0, max_height = max(yheight_line_tag)
    question_set_description_tag['bbox'] = "(%d, %d, %d, %d)" % (x0, y0, max_x0 + max_width, max_y0 + max_height)
    #print question_set_description_index
    return question_set_description_index+index, question_set_description_tag


def get_the_complete_question(index, textline_tags):
    new_textline_tags = textline_tags[index:]
    question_description_content = bs()
    xwidth_line_tag = []
    yheight_line_tag = []
    soup = bs()
    question_tag = soup.new_tag('Question')
    question_description_tag = soup.new_tag('QuestionDescription')
    # options_soup = None
    # options_index = 0
    print 'i want length ', len(new_textline_tags)
    for question_index, line_tag in enumerate(new_textline_tags):
        if question_index == 0:
            x0, width = float(line_tag['x']), float(line_tag['width'])
            y0, height = float(line_tag['y']), float(line_tag['height'])
        textline_text = parse_line_text(line_tag)
        result_option = re.search(TEST_OPTION_REGULAR_EXPRESSION_COMPILED, textline_text)
        print result_option
        if result_option:
            options_index, options_soup = get_all_the_options(question_index, new_textline_tags)
            print 'options soup ', options_soup
            break
        xwidth_line_tag.append((float(line_tag['x']), float(line_tag['width'])))
        yheight_line_tag.append((float(line_tag['y']), float(line_tag['height'])))
        # question_description_content.append(line_tag)
        question_description_content.append(textline_text)
    max_x0, max_width = max(xwidth_line_tag)
    max_y0, max_height = max(yheight_line_tag)
    question_description_tag['bbox'] = "(%d, %d, %d, %d)" % (x0, y0, max_x0 + max_width, max_y0 + max_height)
    question_description_tag.append(question_description_content)
    question_tag.append(question_description_tag)
    question_tag.append(options_soup)
    # print question_tag
    print 'question_index ', question_index
    print 'index inside ', index

    return max(question_index, options_index) + index, question_tag


def get_all_the_options(index, textline_tags):
    new_textline_tags = textline_tags[index:]
    soup = bs()
    options = soup.new_tag('options')
    xwidth_line_tag = []
    yheight_line_tag = []
    #print textline_tags
    # print 'length ', len(new_textline_tags)
    options_value_arr = []

    options_count = 0
    for option_index, line_tag in enumerate(new_textline_tags):
        textline_text = parse_line_text(line_tag)
        result_option = re.search(TEST_OPTION_REGULAR_EXPRESSION_COMPILED, textline_text)
        result_question = re.search(TEST_QUESTION_REGULAR_EXPRESSION_COMPILED, textline_text)
        result_section_title = re.search(TEST_SECTION_TITLE_REGULAR_EXPRESSION, textline_text)
        result_question_set = re.search(QUESTION_SET_REGULAR_EXPRESSION, textline_text)
        if result_option:
            bbox = (float(line_tag['x']),
                    float(line_tag['y']),
                    float(line_tag['x']) + float(line_tag['width']),
                    float(line_tag['y']) + float(line_tag['height'])
                    )
            if result_option.group(0) in FirstOptionCharArr:
                option_class = 'A'
            elif result_option.group(0) in SecondOptionCharArr:
                # options.append(option)
                option_class = 'B'
            elif result_option.group(0) in ThirdOptionCharArr:
                # options.append(option)
                option_class = 'C'
            elif result_option.group(0) in FourthOptionCharArr:
                # options.append(option)
                option_class = 'D'
            elif result_option.group(0) in FifthOptionCharArr:
                # options.append(option)
                option_class = 'E'

            # print option
            option_soup = bs()
            option = option_soup.new_tag('option')
            option.append(textline_text)
            options.append(option)
            option['bbox'] = "(%d, %d, %d, %d)" % bbox

            # print options
        elif result_question or result_section_title or result_question_set:
            break
        else:
            option.append(textline_text)
        #print option_index
    # print options
    return option_index + index, options


def parse_page_with_columns(text_column_tag, inside_question_set_description=False):
    textline_tags = text_column_tag.find_all('textline')
    index = 0
    soup = bs()
    section_tag = None
    question_set_tag = None
    question_tag = None
    print 'length ', len(textline_tags)
    print textline_tags[-1]
    while index < len(textline_tags):
        try:
            print 'length ', len(textline_tags)
            print 'index ', index
            textline_tag = textline_tags[index]
            textline_text = parse_line_text(textline_tag)
            result_option = re.search(TEST_OPTION_REGULAR_EXPRESSION_COMPILED, textline_text)
            result_question = re.search(TEST_QUESTION_REGULAR_EXPRESSION_COMPILED, textline_text)
            result_section_title = re.search(TEST_SECTION_TITLE_REGULAR_EXPRESSION, textline_text)
            result_answer_key = re.search(ANSWER_KEY_REGULAR_EXPRESSION, textline_text)
            result_question_set = re.search(QUESTION_SET_REGULAR_EXPRESSION, textline_text)
            if result_section_title:
                print 'in result section title'
                section_tag = soup.new_tag('Section')
                section_tag['continued'] = 'False'
                index, section_title_tag = get_the_section_title(index, textline_tags)
                section_tag.append(section_title_tag)
            elif result_question_set:
                print 'in result question set'
                if not section_tag:
                    section_tag = soup.new_tag('Section')
                    section_tag['continued'] = 'True'
                question_set_tag = soup.new_tag('QuestionSet')
                question_set_tag['continued'] = 'False'
                index, question_set_description_tag = get_the_complete_question_set_description(index, textline_tags)
                question_set_tag.append(question_set_description_tag)
                section_tag.append(question_set_tag)
            elif result_option:
                if not section_tag:
                    section_tag = soup.new_tag('Section')
                    section_tag['continued'] = 'True'
                if not question_set_tag:
                    question_set_tag = soup.new_tag('QuestionSet')
                    question_set_tag['continued'] = 'True'
                    section_tag.append(question_set_tag)
                if not question_tag:
                    question_tag = soup.new_tag('Question')
                    question_tag['continued'] = 'True'
                    index, options_tag = get_all_the_options(index, textline_tags)
                    question_tag.append(options_tag)
                else:
                    index += 1
            elif result_question:
                print 'in result question'
                if not section_tag:
                    section_tag = soup.new_tag('Section')
                    section_tag['continued'] = 'True'
                if not question_set_tag:
                    if section_tag['continued'] == 'True':
                        question_set_tag = soup.new_tag('QuestionSet')
                        question_set_tag['continued'] = 'True'
                    elif section_tag['continued'] == 'False':
                        question_set_tag = soup.new_tag('QuestionSet')
                        question_set_tag['continued'] = 'False'
                    section_tag.append(question_set_tag)
                print 'index 5 ', index
                index, question_tag = get_the_complete_question(index, textline_tags)
                print 'index 6 ', index
                question_set_tag.append(question_tag)
                # print section_tag
            else:
                index += 1
        except Exception, e:
            print e
            exc_type, exc_obj, tb = sys.exc_info()
            f1 = tb.tb_frame
            lineno = tb.tb_lineno
            filename = f1.f_code.co_filename
            linecache.checkcache(filename)
            line = linecache.getline(filename, lineno, f1.f_globals)
            print 'EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj)
            index += 1
    # print section_tag
    if section_tag:
        return section_tag
    #print 'section_tag ', section_tag


def parse_page(page_tag):
    text_column_tags = page_tag.find_all(TEXTCOLUMN_TAG)
    soup = bs()

    for text_column_tag in text_column_tags:
        if text_column_tag:
            soup.append(text_column_tag)
    parsed_pdf_page = parse_page_with_columns(soup)
    return parsed_pdf_page


def parse_pages(pages_tag):
    page_tags = pages_tag.find_all(PAGE_TAG)
    soup = bs()
    for page_tag in page_tags:
        parsed_page = parse_page(page_tag)
        if parsed_page:
            soup.append(parsed_page)
    return soup

folder_path = '/home/anubhav/Desktop/Work/pdf-engine-workstation/1539/'
start_page_no = 67
end_page_no = 67

for i in range(start_page_no, end_page_no + 1):
    xml_filename = 'XML/1539.' + str(i) + '.xml'
    result_filename = 'XML_RESULT2/result_1539.' + str(i) + '.xml'
    mypath = os.path.join(folder_path, xml_filename)
    result_path = os.path.join(folder_path, result_filename)
    f = codecs.open(result_path, mode='w', encoding='utf-8')
    soup = bs(open(mypath), 'html.parser')
    pages_tags = soup.find_all(PAGES_TAG)
    new_soup = bs(features='xml')
    for pages_tag in pages_tags:
        parsed_pages = parse_pages(pages_tag)
        new_soup.append(parsed_pages)

    f.write(new_soup.prettify(formatter=None))
    f.close()

