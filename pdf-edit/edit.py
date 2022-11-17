import fitz
import json
from pprint import pprint


extr_flags = fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE


class PDFEdit:

    def __init__(self, func=None):
        # if func is None:
        #     raise "func is not None"
        self.func = func

    def __call__(self, fpath):
        doc = fitz.open(fpath)
        self.font_subset = {}
        for page in doc:
            # encode_dict = self.encode(page)
            for b in page.get_text('dict')['blocks']:
                if 'lines' in b:
                    for l in b['lines']:
                        if 'spans' in l:
                            for s in l['spans']:
                                s['text'] = 'aaaaa'
        doc.save('avc.pdf')

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
                for line in getattr(block, 'lines', []):
                    for span in getattr(line, 'spans', []):
                        span_font = span['font']
                        span_font = fitz.Font(fontbuffer=span_font)

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
            page.clean_contents(sanitize=True)
            fontrefs = self.get_page_fontrefs(page)
            if not len(fontrefs):
                continue
            self.cont_clean(page, fontrefs)
            text_writers = {}
            for block in blocks:
                for line in getattr(block, 'lines', []):
                    wmode = line["wmode"]
                    wdir  = list(line["dir"])
                    markup_dir = 0
                    bidi_level = 0
                    if wdir == [0, 1]:
                        markup_dir = 4
                    for span in getattr(line, 'spans', []):
                        span_font = span['font']

                        text = span["text"].replace(chr(0xFFFD), chr(0xB6))
                        textb = text.encode("utf8", errors="backslashreplace")
                        text = textb.decode("utf8", errors="backslashreplace")
                        span["text"] = text

                        if wdir != [1, 0]:
                            self.tilted_span(page, wdir, span, span_font)
                            continue
                        color = span['color']
                        if color in text_writers.keys():
                            tw = text_writers[color]
                        else:
                            tw = fitz.TextWriter(page.rect)
                            text_writers[color] = tw
                        try:
                            tw.appen(
                                span['origin'],
                                text, 
                                font=span_font,
                                fontsize=self.resize(span, span_font)
                            )
                        except:
                            print("===ERROR===")
            for color in text_writers.keys():
                tw = text_writers[color]
                outcolor = fitz.sRGB_to_pdf(color)
                tw.write_text(page, color=outcolor)
            
            self.clean_fontnames(page)
        
            document.save(document.name.replace(".pdf", "-new.pdf"), garbage=4, deflate=True)
                               
    
    def resize(span, font):
        text = span['text']
        rect = fitz.Rect(span['bbox'])
        fsize = span['size']

        tl = font.text_lenght(text, fontsize=fsize)
        if tl <= rect.width:
            return False
        new_size = rect.width / tl * fsize
        return new_size


    def cont_clean(page, fontrefs):

        def remove_font(fontrefs, lines):
            changed = False
            count = len(lines)
            for ref in fontrefs:
                found = False
                for i in range(count):
                    if lines[i] == b"ET":
                        continue
                    if lines[i].endswith(b" Tf"):
                        if lines[i].endswith(ref):
                            found = True
                            lines[i] = b""
                            changed = True
                            continue
                        else:
                            found = False
                            continue
                    if found and (lines[i].endswith(
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
                    )):
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
    
    


    def decode(self, page):
        pass
        

    


if __name__ == "__main__":
    tool = PDFEdit(func=None)
    a = tool(fpath='test.pdf')



