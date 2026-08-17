"""
Strips comments, author names and tracked changes from every .docx and .pptx
found recursively under the source folder. Cleaned copies are written to a
separate folder, leaving the originals untouched.

The technique of unpacking an Office file, editing its XML parts with lxml and
repacking it was learnt in the Data Mining module. The tag lists and the
tracked-deletion handling below are specific to this project's material.
"""

import os
import shutil
import zipfile
import tempfile
from lxml import etree

from config import SOURCE_DIR, CLEANED_DIR

OUTPUT_DIR = CLEANED_DIR

#Namespaces used in Office XML

W_NS  = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14_NS = "http://schemas.microsoft.com/office/word/2010/wordml"
CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"

#Tags to completely remove from Word documents
WORD_REMOVE_TAGS = [
    # Comments
    f"{{{W_NS}}}comment",
    f"{{{W_NS}}}commentRangeStart",
    f"{{{W_NS}}}commentRangeEnd",
    f"{{{W_NS}}}commentReference",
    # Tracked changes (insertions, deletions, moves)
    f"{{{W_NS}}}ins",
    f"{{{W_NS}}}del",
    f"{{{W_NS}}}moveFrom",
    f"{{{W_NS}}}moveTo",
    f"{{{W_NS}}}moveFromRangeStart",
    f"{{{W_NS}}}moveFromRangeEnd",
    f"{{{W_NS}}}moveToRangeStart",
    f"{{{W_NS}}}moveToRangeEnd",
    f"{{{W_NS}}}rPrChange",
    f"{{{W_NS}}}pPrChange",
    f"{{{W_NS}}}sectPrChange",
    f"{{{W_NS}}}tblPrChange",
    f"{{{W_NS}}}trPrChange",
    f"{{{W_NS}}}tcPrChange",
]

# XML part names to blank out (replace with minimal valid XML)
WORD_BLANK_PARTS = [
    "word/comments.xml",
    "word/commentsExtended.xml",
    "word/commentsIds.xml",
    "word/commentsExtensible.xml",
    "word/revisions.xml",
]

PPTX_BLANK_PARTS_PREFIX = [
    "ppt/comments/",        # slide-level comments
]


#Helpers 
def anonymise_core_properties(xml_bytes: bytes) -> bytes:
    """Replace author/creator fields in docProps/core.xml with 'Anonymous'."""
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError:
        return xml_bytes

    author_tags = [
        f"{{{DC_NS}}}creator",
        f"{{{DC_NS}}}description",
        f"{{{CP_NS}}}lastModifiedBy",
        f"{{{CP_NS}}}lastPrinted",
    ]
    for tag in author_tags:
        for el in root.iter(tag):
            el.text = "Anonymous"

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def remove_elements_by_tag(xml_bytes: bytes, tags_to_remove: list) -> bytes:
    """Parse XML and remove every element whose tag is in tags_to_remove."""
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError:
        return xml_bytes

    for tag in tags_to_remove:
        for el in root.iter(tag):
            parent = el.getparent()
            if parent is not None:
                # For tracked deletions, keep the text inside <w:del><w:r><w:delText>
                # by unwrapping child runs, so we keep what was deleted and content
                # is preserved; we just remove the change-tracking markup.
                if el.tag == f"{{{W_NS}}}del":
                    # Preserve del text as normal runs by re-tagging delText to t
                    for delText in el.iter(f"{{{W_NS}}}delText"):
                        delText.tag = f"{{{W_NS}}}t"
                    # Move children up to parent
                    idx = list(parent).index(el)
                    for child in list(el):
                        parent.insert(idx, child)
                        idx += 1
                parent.remove(el)

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def blank_xml_part(part_name: str) -> bytes:
    """Return a minimal valid XML document to replace a comments/revisions part."""
    root_tag_map = {
        "word/comments.xml":             "comments",
        "word/commentsExtended.xml":     "commentsExtended",
        "word/commentsIds.xml":          "commentsIds",
        "word/commentsExtensible.xml":   "commentsExtensible",
        "word/revisions.xml":            "revisions",
    }
    root_tag = root_tag_map.get(part_name, "root")
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:{root_tag} xmlns:w="{ns}"/>'
    ).encode("utf-8")


#Per-format cleaners

def clean_docx(src_path: str, dst_path: str):
    """Strip comments and tracked changes from a .docx file."""
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        # Unzip
        with zipfile.ZipFile(src_path, "r") as z:
            z.extractall(tmp)

        # Walk every XML file inside the unpacked docx
        for root_dir, dirs, files in os.walk(tmp):
            for fname in files:
                fpath = os.path.join(root_dir, fname)
                # Relative path inside the zip (use forward slashes)
                rel = os.path.relpath(fpath, tmp).replace("\\", "/")

                if not fname.endswith(".xml") and not fname.endswith(".rels"):
                    continue

                with open(fpath, "rb") as f:
                    data = f.read()

                # Blank out comment / revision XML parts entirely
                if rel in WORD_BLANK_PARTS:
                    data = blank_xml_part(rel)

                # Anonymise core properties
                elif rel == "docProps/core.xml":
                    data = anonymise_core_properties(data)

                # Strip tracked-change and comment elements from document body
                elif rel in (
                    "word/document.xml",
                    "word/footnotes.xml",
                    "word/endnotes.xml",
                    "word/header1.xml",
                    "word/header2.xml",
                    "word/footer1.xml",
                    "word/footer2.xml",
                ):
                    data = remove_elements_by_tag(data, WORD_REMOVE_TAGS)

                with open(fpath, "wb") as f:
                    f.write(data)

        # Repack into a new zip
        with zipfile.ZipFile(dst_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for root_dir, dirs, files in os.walk(tmp):
                for fname in files:
                    fpath = os.path.join(root_dir, fname)
                    arcname = os.path.relpath(fpath, tmp)
                    zout.write(fpath, arcname)


def clean_pptx(src_path: str, dst_path: str):
    """Strip comments and author metadata from a .pptx file."""
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(src_path, "r") as z:
            z.extractall(tmp)

        for root_dir, dirs, files in os.walk(tmp):
            for fname in files:
                fpath = os.path.join(root_dir, fname)
                rel = os.path.relpath(fpath, tmp).replace("\\", "/")

                if not fname.endswith(".xml"):
                    continue

                with open(fpath, "rb") as f:
                    data = f.read()

                # Drop entire comments parts
                if any(rel.startswith(pfx) for pfx in PPTX_BLANK_PARTS_PREFIX):
                    data = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><root/>'

                # Anonymise core properties
                elif rel == "docProps/core.xml":
                    data = anonymise_core_properties(data)

                with open(fpath, "wb") as f:
                    f.write(data)

        with zipfile.ZipFile(dst_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for root_dir, dirs, files in os.walk(tmp):
                for fname in files:
                    fpath = os.path.join(root_dir, fname)
                    arcname = os.path.relpath(fpath, tmp)
                    zout.write(fpath, arcname)


#Main
def main():
    if not os.path.isdir(SOURCE_DIR):
        print(f"ERROR: Source folder not found:\n  {SOURCE_DIR}")
        return

    processed = 0
    skipped = 0
    errors = []

    for dirpath, dirnames, filenames in os.walk(SOURCE_DIR):
        # Skip if we somehow end up inside the output folder
        if dirpath.startswith(OUTPUT_DIR):
            continue

        for filename in filenames:
            src_path = os.path.join(dirpath, filename)
            ext = os.path.splitext(filename)[1].lower()

            # Compute destination path, mirroring the folder structure
            rel_path = os.path.relpath(src_path, SOURCE_DIR)
            dst_path = os.path.join(OUTPUT_DIR, rel_path)

            if ext == ".docx":
                try:
                    print(f"Cleaning DOCX: {rel_path}")
                    clean_docx(src_path, dst_path)
                    processed += 1
                except Exception as e:
                    print(f"  ERROR: {e}")
                    errors.append((rel_path, str(e)))

            elif ext == ".pptx":
                try:
                    print(f"Cleaning PPTX: {rel_path}")
                    clean_pptx(src_path, dst_path)
                    processed += 1
                except Exception as e:
                    print(f"  ERROR: {e}")
                    errors.append((rel_path, str(e)))

            else:
                # Copy everything else (PDFs, ZIPs, etc.) unchanged
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                shutil.copy2(src_path, dst_path)
                skipped += 1

    print("\n" + "="*60)
    print(f"Done.")
    print(f"  Cleaned (docx/pptx): {processed}")
    print(f"  Copied unchanged:    {skipped}")
    print(f"  Errors:              {len(errors)}")
    if errors:
        print("\nFiles with errors:")
        for rel, msg in errors:
            print(f"  {rel}: {msg}")
    print(f"\nCleaned files saved to:\n  {OUTPUT_DIR}")


if __name__ == "__main__":
    main()