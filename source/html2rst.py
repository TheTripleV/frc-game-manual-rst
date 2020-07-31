from re import L
from typing import List, Union
from bs4 import BeautifulSoup
from bs4 import UnicodeDammit
from bs4 import NavigableString
from bs4 import PageElement, Tag
import bs4
import textwrap
import string
import dashtable

from contextlib import suppress

class SkipNode(Exception): pass
class SkipDeparture(Exception): pass
class SkipSiblings(Exception): pass
class SkipChildren(Exception): pass
class StopTraversal(Exception): pass

def walkabout_funcs(node, venter=None, vleave=None):
    def dummy(*args): pass
    class T:
        enter = venter or dummy
        leave = vleave or dummy
    walkabout(node, T)

def walkabout(node, visitor):
    with suppress(StopTraversal):
        walkabout_helper(node, visitor)

def walkabout_helper(node, visitor):
    # print(node)
    call_leave = True
    with suppress(SkipChildren):
        try:
            visitor.enter(node)
        except SkipNode:
            return
        except SkipDeparture:
            call_leave = False
        with suppress(SkipSiblings):
            try:
                children = node.children
            except AttributeError:
                pass
            else:
                for n in node.children:
                    walkabout(n, visitor)

    if call_leave:
        visitor.leave(node)

def ensure_string(item) -> str:
    if isinstance(item, str):
        return item
    return item.get_text()

def spacing(text) -> str:
    text = ensure_string(text)
    return " " + text + " "


def clean_noln(text) -> str:
    text = ensure_string(text)
    t1 = text.strip(" \r\n").replace("\r", "")
    
    while "  " in t1:
        t1 = t1.replace("  ", " ")

    for char in {"\t", "\x0b", "\x0c", "\xa0"}:
        t1 = t1.replace(char, " ")

    t1 = t1.strip(" ")

    return t1

def clean(text) -> str:
    text = ensure_string(text)
    t1 = text.strip(" \r\n").replace("\r", "")
    
    for char in {"\n", "\t", "\x0b", "\x0c", "\xa0"}:
        t1 = t1.replace(char, " ")
    
    while "  " in t1:
        t1 = t1.replace("  ", " ")

    t1 = t1.strip(" ")

    return t1

def italic(text) -> str:
    text = ensure_string(text)
    ct = clean(text)

    if not ct: return ""
    if not ct.strip(" \r\n\t"): return ""
    
    # Don't allow italicing twice or after bold
    if len(ct) >= 2 and ct[0] == "*" and ct[-1] == "*":
        return ct
    return f"*{ct}*"

def bold(text) -> str:
    text = ensure_string(text)
    ct = clean(text)

    if not ct: return ""
    if not ct.strip(" \r\n\t"): return ""

    # Don't allow bolding twice
    if len(ct) >= 4 and ct[:2] == "**" and ct[-2:] == "**":
        return ct
    # Promote italic to bold (rst doesn't support both)
    elif len(ct) >= 2 and ct[0] == "*" and ct[-1] == "*":
        return f"*{ct}*"

    return f"**{ct}**"

def superscript(text) -> str:
    text = ensure_string(text)
    ct = clean(text)

    if not ct: return ""

    return f"\\ :sup:`{ct}`\\"

def subscript(text) -> str:
    text = ensure_string(text)
    ct = clean(text)

    if not ct: return ""

    return f"\\ :sub:`{ct}`\\"



HEADINGS = {
    "h1" : "#",
    "h2" : "*",
    "h3" : "=",
    "h4" : "-",
    "h5" : "^",
}

def heading(node, heading=None) -> str:
    if not isinstance(node, str) and not heading:
        heading = node.name
    text = ensure_string(node)
    ct = clean(text)
    if heading in HEADINGS:
        return ct + "\n" + len(ct) * HEADINGS[heading]
    else:
        raise ValueError

def image(node) -> str:
    link = None
    if isinstance(node, str):
        link = node
    else:
        link = node.attrs['src']
    
    return f".. image:: {link}"

def inline_link(node) -> str:
    try:
        return f"`{clean(node)} <{node.attrs['href']}>`_ "
    except:
        return clean(node)


def table(node: PageElement) -> str:
    for tag in node.find_all("a"):
        if "href" not in tag.attrs:
            tag.unwrap()

    for tag in node.find_all("b"):
        tag.string = clean(tag)

    for tag in node.find_all("i"):
        tag.string = clean(tag)

    for tag in node.find_all("p"):
        with suppress(Exception):
            tag.string = clean(tag.string)
            if len(tag.string):
                tag.string = tag.string + "\n"

    return dashtable.html2rst(str(node))

def para(node: Union[str, PageElement], ignore_formatting=False) -> str:
    if isinstance(node, str):
        return node

    # Remove formatting from links
    for tag in node.find_all("a"):
        for c in tag.find_all("b"):
            c.unwrap()
        for c in tag.find_all("i"):
            c.unwrap()
        for c in tag.find_all("sup"):
            c.unwrap()
        for c in tag.find_all("sub"):
            c.unwrap()

    # Handle italic, bold, links
    def do(sub: Tag):
        # Blue Boxs have images nested inside paragraphs for some reason
        if sub.name == "img":
            sub.replace_with(
                NavigableString(
                    image(sub).strip() + "__newline____newline__"
                )
            )
        if sub.name == "sup":
            sub.replace_with(
                NavigableString(
                    clean(
                        superscript(
                            sub
                        )
                    )
                )
            )
        if sub.name == "sub":
            sub.replace_with(
                NavigableString(
                    clean(
                        subscript(
                            sub
                        )
                    )
                )
            )
        if sub.name == "i" and not ignore_formatting:
            sub.replace_with(
                NavigableString(
                    spacing(
                        italic(
                            clean(
                                sub
                            )
                        )
                    )
                )
            )
        elif sub.name == "b" and not ignore_formatting:
            sub.replace_with(
                NavigableString(
                    spacing(
                        bold(
                            clean(
                                sub
                            )
                        )
                    )
                )
            )
        elif sub.name == "a":
            sub.replace_with(
                NavigableString(
                    spacing(
                        inline_link(
                            sub
                        )
                    )
                )
            )
    
    walkabout_funcs(node, vleave=do)
    return node.get_text()
        
def admonition(text: Union[str, PageElement], name:str = "note", add_only=False) -> str:
    text = ensure_string(text)
    directive = "" if add_only else f".. {name}::\n"
    return directive + textwrap.indent(text, " " * 4, predicate=lambda x: True)

def admonition_add(text: Union[str, PageElement]) -> str:
    text = ensure_string(text)
    return textwrap.indent(text, " " * 4, predicate=lambda x: True)


class Docs:
    def __init__(self) -> None:
        self.pages: List[str] = []

    def new_page(self):
        self.pages.append("")

    def has_page(self):
        return bool(self.pages)

    def __iadd__(self, text):
        self.pages[-1] += text
        return self

    def __ifloordiv__(self, num):
        self.pages[-1] += "\n" * num
        return self


class Visitor:
    def __init__(self, docs: Docs) -> None:
        self.docs = docs

        self.in_p = False

    def enter(self, node: PageElement):
        
        if node.name == "h1":
            self.docs.new_page()

        if not self.docs.has_page():
            return

        if node.name in HEADINGS:
            self.docs += heading(node)
            self.docs //= 3

        if node.name == "img":
            self.docs += image(node)
            self.docs //= 2

        if node.name == "table":
            self.docs += table(node)
            self.docs //= 3

            raise SkipNode
        
        
        if node.name == "p":
            if "class" in node.attrs:

                for c in node.attrs["class"]:
                    if "Box" in c:
                        continuation = False
                        with suppress(Exception):
                            for cc in node.previous_sibling.attrs["class"]:
                                if "Box" in cc:
                                    continuation = True

                        with suppress(Exception):
                            for cc in node.previous_sibling.previous_sibling.attrs["class"]:
                                if "Box" in cc:
                                    continuation = True

                        self.docs += admonition(
                            para(node).strip(" "),
                            "note",
                            add_only=continuation
                        )
                        self.docs //= 2

                        # if continuation:
                        #     self.docs += admonition_add(
                        #         para(node).strip(" ")
                        #     )
                        #     self.docs //= 2
                        # else:
                        #     self.docs += admonition(
                        #         para(node).strip(" "),
                        #         "note"
                        #     )
                        #     self.docs //= 2
                        return

                if "SafetyRule" in node.attrs["class"]:

                    for tag in node.find_all("b"):
                        tag.unwrap()
                        break

                    # Find 2nd period
                    btext = ""
                    text = ""
                    sents = [t + "." for t in para(node).split(".")]
                    for idx, sent in enumerate(sents):
                        if idx <= 1:
                            btext += spacing(sent)
                        else:
                            text += sent
                    self.docs += clean(spacing(bold(btext)) + text)
                    self.docs //= 2
                else:
                    self.docs += clean(para(node))
                    self.docs //= 2                    
            else:
                self.docs += clean(para(node))
                self.docs //= 2

    def leave(self, node): pass



with open("./game_manual/html.htm", "r", encoding="windows-1252") as file:
    html = file.read()

dammit = UnicodeDammit(html, ["windows-1252"],)

html_uni = dammit.unicode_markup

soup = BeautifulSoup(html_uni)

# PREPROCESSING

# Remove non links
for tag in soup.find_all("a"):
    if "href" not in tag.attrs:
        tag.unwrap()

# Combine consecutive bolds
for tag in soup.find_all("b"):
    with suppress(Exception):
        if tag.next_sibling.name == "b":
            tag.string = tag.string + tag.next_sibling.string
            tag.next_sibling.decompose()

# Combine consecutive italics
for tag in soup.find_all("i"):
    with suppress(Exception):
        if tag.next_sibling.name == "i":
            tag.string = tag.string + tag.next_sibling.string
            tag.next_sibling.decompose()

# PROCESSING
d = Docs()
v = Visitor(d)
walkabout(soup, v)

# POST PROCESSING

# dont allow bold images ???
for i in range(len(d.pages)):
    d.pages[i] = d.pages[i].replace("**.. image::", ".. image::")
    for ext in {"png", "jpg", "jpeg"}:
        d.pages[i] = d.pages[i].replace(f"{ext}**", ext)
    d.pages[i] = d.pages[i].replace("\n**\n", "\n\n")
    d.pages[i] = d.pages[i].replace("__newline__**", "__newline__")

# fix images with text without a newline
for i in range(len(d.pages)):
    d.pages[i] = d.pages[i].replace("__newline__", "\n")

# fix broken indentation
loc = 0
for i in range(len(d.pages)):
    lines = d.pages[i].split("\n")
    for j in range(len(lines)):
        with suppress(Exception):
            if lines[j][0] == " " and lines[j][1] != " ":
                lines[j] = lines[j][1:]

    d.pages[i] = "\n".join(lines)


# fix links
for i in range(len(d.pages)):
    d.pages[i] = d.pages[i].replace("./html_files", "../game_manual/html_files")

for idx, page in enumerate(d.pages):
    with open(f"./gen/section_{idx+1}.rst" , "w") as f:
        f.write(page)