#!/usr/bin/python
# -*- coding: utf-8 -*-

import os, sys, re
import math
import numpy as np
import csv

def create_files(folder_path):
    xml_folder = os.path.join(folder_path,'extract/xml/')
    #print xml_folder
    xml_files = os.listdir(xml_folder)
    no_of_pages = len(xml_files)    
    pages = range(1,no_of_pages+1)
    sorted_pages = ['page_'+str(p)+'.xml' for p in pages]
    file_paths = [os.path.join(xml_folder,xf) for xf in sorted_pages]
    return file_paths
    
def get_header_footer(file_paths,toc_page):
    header_footer = []
    for f in file_paths:
        stream = open(f,'r').read()
        header_footer.append(re.findall("<textword .*>\n<text>(\d+)</text>",stream))
    
    hf_l = len(header_footer)-1
    print 'lenght of header_footer = ',hf_l
    last_page = hf_l
    page_numbers = [0]*(hf_l+1)
    
    while hf_l >= 0:
        if header_footer[hf_l] != []:
            last_page = int(header_footer[hf_l][0])
            break
        else:
            hf_l = hf_l-1
            
    max_page = hf_l
            
    while hf_l >= 0:
        print 'hf_l = ',hf_l
        print 'last_page = ', last_page
        page_numbers[hf_l] = last_page
        hf_l -= 1
        last_page -=1
        
    if page_numbers[0] == 0:
        page_numbers = range(1,max_page+1)
        
    ref_header_footer = []
    for x in header_footer:
        if x != []:
            ref_header_footer.append(int(x[0]))
        else:
            ref_header_footer.append(0)
    
    return ref_header_footer, page_numbers

average = lambda x: sum(x) * 1.0 / len(x)
variance = lambda x: map(lambda y: (y - average(x)) ** 2, x)
stdev = lambda x: math.sqrt(average(variance(x)))

def get_headings(bold_headings):
    ch_headings = []
    i = 1
    for bh in bold_headings:
        #print "page no",i
        i += 1
        yvalues = []
        for tu in bh:
            m = re.search("height=\"(\d+)\.\d+\"",tu[0])
            if m:
                yvalues.append(int(m.group(1)))
                
        heading = ''
        
        if yvalues != []:
            ymin = np.array(yvalues).max()
            #print ymin
            for y,ys in enumerate(yvalues):
                if ys == ymin:
                    heading += bh[y][1]
                
        ch_headings.append(heading)
    
    return ch_headings

def get_pattern(folder,file_paths,toc_page):
    bold_headings = []
    bold_texts = []
    header_footer = []    
    for f in file_paths:
        stream = open(f,'r').read()
        bold_headings.append(re.findall("<textword (.*)>\n<text>([^0-9]*)</text>\n<glyph.*style=\".*Bold.*\"",stream))
        bold_texts.append(re.findall("<textline (.*)>\n<textword .*>\n<text>.*</text>\n<glyph.*style=\".*Bold.*\"",stream))
        header_footer.append(re.findall("<textword .*>\n<text>(\d+)</text>",stream))
    
    y_values = []
    height_values = []
    chapter_names = get_headings(bold_headings)
    
    for bt in bold_texts:
        page_heights = []        
        page_ys = []
        for lines in bt:
            #print lines
            m = re.search("height=\"(\d+)\.\d+\"",lines)
            if m:
                #print m.group(1)
                page_heights.append(int(m.group(1)))
            #page_heights.append(int(lines.split("\" ")[1].split("=\"")[1].split(".")[0]))
            page_ys.append(int(lines.split("y=\"")[1][:-1].split(".")[0]))
        if len(page_heights) != 0:
            height_max = np.array(page_heights).max()
            y_values.append(page_ys[page_heights.index(height_max)])
        else:
            height_max = 0
            y_values.append(0)
        height_values.append(height_max)
    
    chapter_candidates = []
    content_heights = height_values[toc_page:]
    heading_height = np.array(content_heights).max()
    if content_heights.count(heading_height) == 1:
                heading_height = np.partition(content_heights,len(content_heights)-2)[len(content_heights)-2]
    for h, hv in enumerate(content_heights):
        if hv == heading_height or hv >= (heading_height-2):
            chapter_candidates.append(h+toc_page+1)
            
    heading_candidtates_ind = []
    for cc in chapter_candidates:
        heading_candidtates_ind.append(cc-1)
    candidate_headings = [chapter_names[i] for i in heading_candidtates_ind]
    
    return chapter_candidates, candidate_headings
    

def main(folder,outputfile,toc_page):
    file_paths = create_files(folder)
    #header_footer, page_numbers = get_header_footer(file_paths,toc_page)
    chapter_candidates, chapter_names = get_pattern(folder,file_paths,int(toc_page))
    Resultfile = open(outputfile,'wb')
    wr = csv.writer(Resultfile,dialect='excel')
    #Titles = ["Chapter No","Chapter Name","From","To"]
    Titles = ["start","end","toc","unicode_title"]
    wr.writerow(Titles)
    #Rows = []
    for i in range(len(chapter_candidates)-1):
        #print "Chapter %d is from at Page %d to Page %d"%(i+1,chapter_candidates[i],chapter_candidates[i+1]-1)
        #l = [i+1,chapter_names[i],chapter_candidates[i],chapter_candidates[i+1]-1]
        l = [chapter_candidates[i],chapter_candidates[i+1]-1,'true',chapter_names[i]]
        wr.writerow(l)
        #Rows.append(l)
        #print "Chapter %d is from at Page %d to Page %d"%(i+1,page_numbers[chapter_candidates[i]-1],page_numbers[chapter_candidates[i+1]-1]-1)
    #print "Chapter %d is from at Page %d to Page %d"%(i+2,page_numbers[chapter_candidates[i+1]-1],page_numbers[-1])
    #print "Chapter %d is from at Page %d to Page %d"%(i+2,chapter_candidates[i+1],len(file_paths))
    #l = [i+2,chapter_names[i+1],chapter_candidates[i+1],len(file_paths)]
    l = [chapter_candidates[i+1],len(file_paths),'true',chapter_names[i+1]]
    wr.writerow(l)
    Resultfile.close()

if __name__ == '__main__':
    main(sys.argv[1],sys.argv[2],sys.argv[4])



