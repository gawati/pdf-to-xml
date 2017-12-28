import os
from flask import Flask, request, jsonify
from PyPDF2 import PdfFileWriter, PdfFileReader
import pp
from testprep_pdf2txt import main

__author__ = 'Anubhav Maity'

app = Flask(__name__)


@app.route('/')
def hello_world():
    return 'Welcome to PDF Engine'


@app.route('/splitPDF', methods=['POST'])
def split_the_pdf():
    try:
        print os.getcwd()
        # get the json
        content = request.json
        source_file = content['source']
        target_directory = content['targetDir']

        source_filename = os.path.basename(source_file)
        input_pdf = PdfFileReader(open(source_file, "rb"))
        print source_filename
        source_filename_without_suffix = os.path.splitext(source_filename)[0]
        print source_filename_without_suffix
        filename_suffix = os.path.splitext(source_filename)[1]
        print filename_suffix
        target_filename_list = []
        for i in xrange(input_pdf.numPages):
            output = PdfFileWriter()
            output.addPage(input_pdf.getPage(i))
            target_filename = os.path.join(target_directory, source_filename_without_suffix + '.'
                                           + str(i) + filename_suffix)
            target_filename_list.append(target_filename)
            with open(target_filename, "wb") as outputStream:
                output.write(outputStream)
        mine_pdf(target_filename_list)
        return 'Success'

    except Exception, e:
        print e


@app.route('/minePDF', methods=['POST'])
def mine_pdf(target_filename_list):
    ppservers = ()
    jobs = []
    job_server = pp.Server(ppservers=ppservers)
    for target_filename in target_filename_list:
        output_filename = os.path.basename(target_filename)
        output_path = os.path.dirname(target_filename)
        output_filename_without_suffix = os.path.splitext(output_filename)[0]
        output_path_xml = os.path.join(output_path, 'XML/')
        if not os.path.exists(output_path_xml):
            os.makedirs(output_path_xml)
        output_filename_xml = os.path.join(output_path_xml , output_filename_without_suffix + '.xml')
        print os.getcwd()
        argv_str = ['testprep_pdf2txt.py', '-t', 'xml', '-O', output_path, '-o', output_filename_xml,
                    target_filename]
        jobs.append(job_server.submit(main, (argv_str,), (), ()))
        job_server.print_stats()
    for job in jobs:
        result = job()
        if result:
            break

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7001, debug=True)