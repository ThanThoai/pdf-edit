import fitz

doc = fitz.open("test.pdf")

page = doc[0]

print(page.get_fonts(full=True))