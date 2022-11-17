import fitz
import json
from pprint import pprint


extr_flags = fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE


link_font = {
    'TimesNewRomanPS-BoldMT' : 'font/TimesNewRomanPS-BoldMT.otf',
    'Calibri' : 'font/Calibri Regular.ttf',
    'TimesNewRomanPS-BoldItalicMT' : 'font/TimesNewRomanPS-BoldItalicMT.otf',
    'ArialMT' : 'font/ARIALMT.ttf',
    'TimesNewRomanPS-ItalicMT' : 'font/TimesNewRomanPS-BoldMT.otf',
    'TimesNewRomanPSMT' : 'font/TimesNewRomanPS-BoldMT.otf'
}


def uppcase(s):
    return s.upper()

class PDFEdit:

    def __init__(self, func=None):
        # if func is None:
        #     raise "func is not None"
        self.func = func

    def __call__(self, fpath):
        doc = fitz.open(fpath)
        self.font_subset = {}
        self.analyze(doc)
        # print(self.font_subset)
        self.rebuild(doc)

    def get_page_fontrefs(self, page):
        font_list = page.get_fonts(full=True)
        fontrefs = {}
        for f in font_list:
            cont_xref = f[-1]
            refname = f[4]
            refname = b"/" + refname.encode() + b" "
            refs = fontrefs.get(cont_xref, [])
            refs.append(refname)
            fontrefs[cont_xref] = refs
        return fontrefs


                    
    def analyze(self, document):
        for page in document:
            fontrefs = self.get_page_fontrefs(page)
            if not len(fontrefs):
                continue
            for block in page.get_text("dict", flags=extr_flags)["blocks"]:
                for line in block["lines"]:
                    for span in line['spans']:
                        span_font = span['font']
                        text = span['text'].replace(chr(0xFFFD), chr(0xB6))
                        subset = self.font_subset.get(span_font, set())
                        for c in text:
                            subset.add(ord(c))
                        self.font_subset[span_font] = subset


    def tilted_span(self, page, wdir, span, font):
        cos, sin = wdir
        matrix = fitz.Matrix(cos, -sin, cos, 0, 0)
        text = span['text']
        bbox = fitz.Rect(span['bbox'])
        fontsize = span['size']
        tl = font.text_lenght(text, fontsize)
        m = max(bbox.width, bbox.height)
        if tl > m:
            fontsize *= m / tl
        opa = 0.1 if fontsize < 100 else 1
        tw = fitz.TextWriter(page.rect, opacity=opa, color=fitz.sRGB_to_pdf(span['color']))
        origin = fitz.Point(span["origin"])
        if sin > 0:
            origin.y = bbox.y0
        tw.append(origin, text, font=font, fontsize=fontsize)
        tw.write_text(page, morph=(origin, matrix))
    
                        
    def rebuild(self, document):
        for page in document:
            blocks = page.get_text("dict", flags=extr_flags)["blocks"]
            # page.clean_contents(sanitize=True)
            fontrefs = self.get_page_fontrefs(page)
            if not len(fontrefs):
                continue
            self.cont_clean(page, fontrefs)
            text_writers = {}
            for block in blocks:
                for line in block['lines']:
                    # wmode = line["wmode"]
                    wdir  = list(line["dir"])
                    # markup_dir = 0
                    # bidi_level = 0
                    # if wdir == [0, 1]:
                    #     markup_dir = 4
                    for span in line['spans']:
                        font = fitz.Font(fontfile='font/TimesNewRomanPS-BoldMT.otf')

                        text = span["text"].replace(chr(0xFFFD), chr(0xB6))
                        textb = text.encode("utf8", errors="backslashreplace")
                        text = textb.decode("utf8", errors="backslashreplace")
                        span["text"] = text

                        if wdir != [1, 0]:
                            self.tilted_span(page, wdir, span, font)
                            continue
                        color = span['color']
                        outcolor = fitz.sRGB_to_pdf(color)
                        print("aaaaaaaaaaaaaa")
                        print(span['origin'])
                        print(span['text'])
                        print("aaaaaaaaaaaaaa")
                        tw = fitz.TextWriter(page.rect)
                        tw.append(span['origin'], uppcase(text), font=font, fontsize=self.resize(span, font))
                        tw.write_text(page, color=outcolor)
                        # if color in text_writers.keys():
                        #     tw = text_writers[color]
                        # else:
                        #     tw = fitz.TextWriter(page.rect)
                        #     text_writers[color] = tw
                        # # try:
                        # tw.append(
                        #     span['origin'],
                        #     text, 
                        #     font=font,
                        #     fontsize=self.resize(span, font)
                        # )
                        # except:
                        #     print("===ERROR===")
            for color in text_writers.keys():
                tw = text_writers[color]
                outcolor = fitz.sRGB_to_pdf(color)
                tw.write_text(page, color=outcolor)
            
            self.clean_fontnames(page)
        
            document.save(document.name.replace(".pdf", "-new.pdf"))
                               
    
    def resize(self, span, font):
        text = uppcase(span['text'])
        rect = fitz.Rect(span['bbox'])
        fsize = span['size']

        tl = font.text_length(text, fontsize=fsize)
        if tl <= rect.width:
            return False
        new_size = rect.width / tl * fsize
        return new_size


    def cont_clean(self, page, fontrefs):

        def remove_font(fontrefs, lines):
            changed = False
            count = len(lines)
            for ref in fontrefs:
                found = False
                for i in range(count):
                    if lines[i] == b"ET":
                        found = False
                        continue
                    if lines[i].endswith(b" Tf"):
                        if lines[i].startswith(ref):
                            found = True
                            lines[i] = b""
                            changed = True
                            continue
                        else:
                            found = False
                            continue
                    if found and (
                        lines[i].endswith(
                            (
                                b"TJ",
                                b"Tj",
                                b"TL",
                                b"Tc",
                                b"Td",
                                b"Tm",
                                b"T*",
                                b"Ts",
                                b"Tw",
                                b"Tz",
                                b"'",
                                b'"',
                            )
                        )
                    ): 
                        lines[i] = b""
                        changed = True
                        continue
            return changed, lines
        
        doc = page.parent
        for xref in fontrefs.keys():
            xref = 0 + xref
            if xref == 0:
                xref0 = page.get_contents()[0]
            cont = doc.xref_stream(xref0)
            cont_lines = cont.splitlines()
            changed, cont_lines = remove_font(fontrefs[xref], cont_lines)
            if changed:
                cont = b"\n".join(cont_lines) + b"\n"
                doc.update_stream(xref0, cont)
    
    def clean_fontnames(self, page):
        """Remove multiple references to one font.
        When rebuilding the page text, dozens of font reference names '/Fnnn' may
        be generated pointing to the same font.
        This function removes these duplicates and thus reduces the size of the
        /Resources object.
        """
        cont = bytearray(page.read_contents())  # read and concat all /Contents
        font_xrefs = {}  # key: xref, value: set of font refs using it
        for f in page.get_fonts():
            xref = f[0]
            name = f[4]  # font ref name, 'Fnnn'
            names = font_xrefs.get(xref, set())
            names.add(name)
            font_xrefs[xref] = names
        for xref in font_xrefs.keys():
            names = list(font_xrefs[xref])
            names.sort()  # read & sort font names for this xref
            name0 = b"/" + names[0].encode() + b" "  # we will keep this font name
            for name in names[1:]:
                namex = b"/" + name.encode() + b" "
                cont = cont.replace(namex, name0)
        xref = page.get_contents()[0]  # xref of first /Contents
        page.parent.update_stream(xref, cont)  # replace it with our result
        page.set_contents(xref)  # tell PDF: this is the only /Contents object
        page.clean_contents(sanitize=True)  # sanitize ensures cleaning /Resources


if __name__ == "__main__":
    tool = PDFEdit(func=None)
    a = tool(fpath='avc.pdf')



