This is a fork of the [pdfminer](https://github.com/euske/pdfminer) tool, with a specific focus on extracting semantic XML out of OCR-ed PDF. 

It extracts pdf content page by page, and also identifies words and lines using distinct tags. 

## Installation

```
python lc_setup.py install
```

You can also install it within a virtualenv.

## Running

```
python lc_pdf2txt.py
```

Provides various options, of interest to us are XML specific options which have been added: 

```
-B make_brief
```

Which disables character level font glyphs if that is too verbose for you. 

```
-t xml
```

Outputs XML 

