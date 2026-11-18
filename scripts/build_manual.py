#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a CPCC software manual (docx) from a structured config.

The config can be JSON or Markdown.

JSON schema:
    {
      "name": "智能排课管理系统",
      "version": "V1.0",
      "owner": "张三、李四",
      "date": "2026-11-18",
      "title": "软件说明书",
      "sections": [
        {"title": "1 软件概述",
         "paragraphs": ["正文段落"],
         "images": [{"path": "07_截图/01_启动页.png", "caption": "图 1 启动页"}]}
      ]
    }

Markdown schema:
    - 软件全称: 智能排课管理系统
    - 版本号: V1.0
    - 著作权人: 张三、李四
    - 日期: 2026-11-18

    ## 1 软件概述

    正文段落。

    ![图 1 启动页](07_截图/01_启动页.png)

The docx contains a standard cover, a header with software name and version,
page number footer, and centered images scaled to keep their aspect ratio.
When Microsoft Word (COM) or LibreOffice is available, the same manual is
exported to PDF next to the docx.

Usage:
    python build_manual.py --config 软著材料/manual.json
    python build_manual.py --config 软著材料/manual.md --no-pdf
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
IMAGE_RE = re.compile(r"^\s*!\[(.*?)\]\((.+?)\)\s*$")
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
TITLE_RE = re.compile(r"^#\s+(.+?)\s*$")
META_RE = re.compile(
    r"^\s*[-*]?\s*(软件全称|软件名称|名称|版本号|版本|著作权人|申请人|日期|编制日期|标题)\s*[:：]\s*(.+?)\s*$"
)

META_MAP = {
    "软件全称": "name", "软件名称": "name", "名称": "name",
    "版本号": "version", "版本": "version",
    "著作权人": "owner", "申请人": "owner",
    "日期": "date", "编制日期": "date", "标题": "title",
}

CJK_FONT = "宋体"
CJK_BOLD = "黑体"


@dataclass
class Section:
    title: str
    paragraphs: list[str] = field(default_factory=list)
    images: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class Manual:
    name: str
    version: str
    owner: str
    when: str
    title: str
    sections: list[Section]


def die(msg: str, code: int = 1) -> None:
    print("[ERROR] " + msg, file=sys.stderr)
    raise SystemExit(code)


def warn(msg: str) -> None:
    print("[WARN] " + msg)


def clean_inline(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^\s*[-*]\s+", "", text)
    return text.strip()


def parse_markdown(path: Path) -> Manual:
    text = path.read_text(encoding="utf-8-sig")
    meta: dict[str, str] = {}
    sections: list[Section] = []
    current: Section | None = None
    buffer: list[str] = []
    title = ""

    def flush() -> None:
        nonlocal buffer
        body = clean_inline("\n".join(buffer))
        buffer = []
        if not body:
            return
        if current is None:
            sections.append(Section(title="", paragraphs=[body]))
        else:
            current.paragraphs.append(body)

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush()
            continue
        meta_match = META_RE.match(line)
        if meta_match and not sections and current is None:
            key = META_MAP[meta_match.group(1)]
            meta[key] = meta_match.group(2).strip()
            continue
        heading = HEADING_RE.match(line)
        if heading:
            flush()
            current = Section(title=heading.group(1).strip())
            sections.append(current)
            continue
        title_match = TITLE_RE.match(line)
        if title_match:
            flush()
            if not sections:
                title = title_match.group(1).strip()
            continue
        image = IMAGE_RE.match(line)
        if image:
            flush()
            if current is None:
                current = Section(title="")
                sections.append(current)
            current.images.append((image.group(2).strip(), image.group(1).strip()))
            continue
        buffer.append(line)

    flush()
    if not sections:
        die("markdown config has no sections: %s" % path)

    return Manual(
        name=meta.get("name", ""),
        version=meta.get("version", "V1.0"),
        owner=meta.get("owner", ""),
        when=meta.get("date", date.today().isoformat()),
        title=meta.get("title", title or "软件说明书"),
        sections=sections,
    )


def parse_json(path: Path) -> Manual:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        die("invalid json config: %s" % exc)
    sections = []
    for index, raw in enumerate(data.get("sections") or [], start=1):
        if not isinstance(raw, dict):
            die("section %d must be an object" % index)
        paragraphs = raw.get("paragraphs") or []
        if isinstance(paragraphs, str):
            paragraphs = [paragraphs]
        images = []
        if raw.get("image"):
            images.append((raw["image"], raw.get("caption", "")))
        for item in raw.get("images") or []:
            if isinstance(item, str):
                images.append((item, ""))
            elif isinstance(item, dict):
                images.append((item.get("path", ""), item.get("caption", "")))
        sections.append(Section(
            title=str(raw.get("title", "")).strip(),
            paragraphs=[clean_inline(str(p)) for p in paragraphs if str(p).strip()],
            images=images,
        ))
    if not sections:
        die("json config has no sections: %s" % path)
    return Manual(
        name=str(data.get("name", "")).strip(),
        version=str(data.get("version", "V1.0")).strip(),
        owner=str(data.get("owner", "")).strip(),
        when=str(data.get("date") or date.today().isoformat()).strip(),
        title=str(data.get("title") or "软件说明书").strip(),
        sections=sections,
    )


def load_config(path: Path) -> Manual:
    if path.suffix.lower() == ".json":
        return parse_json(path)
    if path.suffix.lower() in {".md", ".markdown"}:
        return parse_markdown(path)
    die("config must be .json or .md: %s" % path)


def resolve_image(path_text: str, config_dir: Path, out_dir: Path) -> Path:
    raw = Path(path_text).expanduser()
    candidates = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates += [config_dir / raw, Path.cwd() / raw, out_dir / raw]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    die("image not found: %s (looked in %s)" % (
        path_text, ", ".join(str(c) for c in candidates)))


def image_size_px(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image
        with Image.open(path) as img:
            return img.size
    except Exception:  # noqa: BLE001
        return (0, 0)


def set_run_font(run, name: str, size_pt: float, bold: bool = False) -> None:
    from docx.oxml.ns import qn
    from docx.shared import Pt

    run.font.name = name
    run.font.size = Pt(size_pt)
    run.bold = bold
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)


def add_field(paragraph, instruction: str, placeholder: str = "1") -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = placeholder
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for node in (begin, instr, separate, text, end):
        run._r.append(node)


def build_docx(manual: Manual, out_path: Path, config_dir: Path,
               max_w_cm: float, max_h_cm: float) -> int:
    try:
        import docx
        from docx.enum.section import WD_SECTION
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Cm, Pt
    except ImportError:
        die("python-docx is required: pip install python-docx")

    doc = docx.Document()
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.4)
    section.bottom_margin = Cm(2.2)
    section.left_margin = Cm(2.6)
    section.right_margin = Cm(2.4)
    section.different_first_page_header_footer = True

    normal = doc.styles["Normal"]
    normal.font.name = CJK_FONT
    normal.font.size = Pt(10.5)
    from docx.oxml.ns import qn
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), CJK_FONT)
    normal.paragraph_format.line_spacing = 1.5

    # header: software name and version, every page except the cover
    header = section.header
    hp = header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(hp.add_run("%s %s" % (manual.name, manual.version)), CJK_FONT, 9)
    first_header = section.first_page_header
    first_header.paragraphs[0].text = ""

    # footer: page X of Y
    footer = section.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(fp.add_run("第 "), CJK_FONT, 9)
    add_field(fp, "PAGE")
    set_run_font(fp.add_run(" 页 / 共 "), CJK_FONT, 9)
    add_field(fp, "NUMPAGES")
    set_run_font(fp.add_run(" 页"), CJK_FONT, 9)
    section.first_page_footer.paragraphs[0].text = ""

    # cover
    for _ in range(6):
        doc.add_paragraph("")
    cover = doc.add_paragraph()
    cover.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(cover.add_run(manual.name), CJK_BOLD, 26, bold=True)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(sub.add_run(manual.title), CJK_BOLD, 20, bold=True)

    ver = doc.add_paragraph()
    ver.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(ver.add_run("版本号 " + manual.version), CJK_FONT, 14)

    for _ in range(4):
        doc.add_paragraph("")

    if manual.owner:
        owner_para = doc.add_paragraph()
        owner_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_run_font(owner_para.add_run("著作权人: " + manual.owner), CJK_FONT, 12)
    date_para = doc.add_paragraph()
    date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(date_para.add_run("日期: " + manual.when), CJK_FONT, 12)

    doc.add_page_break()

    image_no = 0
    for sec in manual.sections:
        if sec.title:
            heading = doc.add_paragraph()
            heading.paragraph_format.space_before = Pt(12)
            heading.paragraph_format.space_after = Pt(6)
            heading.paragraph_format.keep_with_next = True
            set_run_font(heading.add_run(sec.title), CJK_BOLD, 15, bold=True)

        for para_text in sec.paragraphs:
            para = doc.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.LEFT
            para.paragraph_format.first_line_indent = Pt(21)
            para.paragraph_format.space_after = Pt(4)
            set_run_font(para.add_run(para_text), CJK_FONT, 10.5)

        for raw_path, caption in sec.images:
            image_path = resolve_image(raw_path, config_dir, out_path.parent)
            if image_path.suffix.lower() not in IMAGE_EXTS:
                die("unsupported image format: %s" % image_path)
            width_px, height_px = image_size_px(image_path)
            pic_para = doc.add_paragraph()
            pic_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            pic_para.paragraph_format.space_before = Pt(6)
            pic_para.paragraph_format.space_after = Pt(4)
            pic_para.paragraph_format.keep_with_next = True
            run = pic_para.add_run()
            if width_px and height_px:
                ratio = height_px / float(width_px)
                width_cm = max_w_cm
                height_cm = width_cm * ratio
                if height_cm > max_h_cm:
                    height_cm = max_h_cm
                    width_cm = height_cm / ratio
                run.add_picture(str(image_path), width=Cm(width_cm), height=Cm(height_cm))
            else:
                run.add_picture(str(image_path), width=Cm(max_w_cm))

            image_no += 1
            cap_text = (caption or "图 %d %s" % (image_no, image_path.stem)).strip()
            cap = doc.add_paragraph()
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cap.paragraph_format.space_after = Pt(10)
            set_run_font(cap.add_run(cap_text), CJK_FONT, 9)

    props = doc.core_properties
    props.title = "%s %s" % (manual.name, manual.title)
    props.subject = "计算机软件著作权登记说明书"
    props.author = manual.owner or manual.name
    props.comments = "Generated by Cn_Software_Copyright skill"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return image_no


def export_pdf_word(docx_path: Path, pdf_path: Path) -> str | None:
    try:
        import win32com.client  # type: ignore
    except ImportError:
        return None
    try:
        word = win32com.client.DispatchEx("Word.Application")
    except Exception:  # noqa: BLE001
        return None
    try:
        word.Visible = False
        word.DisplayAlerts = 0
        document = word.Documents.Open(str(docx_path.resolve()))
        document.SaveAs(str(pdf_path.resolve()), FileFormat=17)
        document.Close(0)
        return "word"
    except Exception as exc:  # noqa: BLE001
        warn("Word COM export failed: %s" % exc)
        return None
    finally:
        try:
            word.Quit()
        except Exception:  # noqa: BLE001
            pass


def find_word_exe() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(
                        root, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Winword.exe") as key:
                    path = winreg.QueryValue(key, None)
                if path and Path(path).exists():
                    return path
            except OSError:
                continue
    except ImportError:
        pass
    return shutil.which("winword")


def export_pdf_word_powershell(docx_path: Path, pdf_path: Path) -> str | None:
    """Fallback for Word installations without pywin32, driven by PowerShell COM."""
    if not find_word_exe():
        return None
    shell = shutil.which("powershell") or shutil.which("pwsh")
    if not shell:
        return None
    import tempfile

    script = (
        '$ErrorActionPreference = "Stop"\n'
        '$word = New-Object -ComObject Word.Application\n'
        '$word.Visible = $false\n'
        '$word.DisplayAlerts = 0\n'
        '$doc = $word.Documents.Open("%s")\n'
        '$doc.SaveAs([ref]"%s", [ref]17)\n'
        '$doc.Close(0)\n'
        '$word.Quit()\n'
    ) % (docx_path.resolve(), pdf_path.resolve())
    temp_path = Path(tempfile.gettempdir()) / "cpcc_manual_export.ps1"
    try:
        temp_path.write_text(script, encoding="utf-8-sig")
        subprocess.run([shell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                        "-File", str(temp_path)],
                       check=False, capture_output=True, timeout=300)
    except Exception as exc:  # noqa: BLE001
        warn("Word PowerShell export failed: %s" % exc)
        return None
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass
    return "word" if pdf_path.exists() else None


def find_soffice() -> str | None:
    found = shutil.which("soffice")
    if found:
        return found
    candidates = [
        r"C:/Program Files/LibreOffice/program/soffice.exe",
        r"C:/Program Files (x86)/LibreOffice/program/soffice.exe",
        "/usr/bin/soffice",
        "/usr/local/bin/soffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def export_pdf_libreoffice(docx_path: Path, out_dir: Path) -> str | None:
    soffice = find_soffice()
    if not soffice:
        return None
    try:
        subprocess.run([soffice, "--headless", "--norestore", "--convert-to", "pdf",
                        "--outdir", str(out_dir), str(docx_path)],
                       check=False, capture_output=True, timeout=300)
    except Exception as exc:  # noqa: BLE001
        warn("LibreOffice export failed: %s" % exc)
        return None
    produced = out_dir / (docx_path.stem + ".pdf")
    return "libreoffice" if produced.exists() else None


def pdf_page_count(pdf_path: Path) -> int:
    try:
        import fitz  # type: ignore
        with fitz.open(str(pdf_path)) as doc:
            return doc.page_count
    except Exception:  # noqa: BLE001
        return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build a CPCC software manual docx from a JSON or Markdown config.")
    p.add_argument("--config", required=True, help="section config, .json or .md")
    p.add_argument("--out-dir", default="软著材料", help="output directory")
    p.add_argument("--name", default=None, help="override software full name")
    p.add_argument("--version", default=None, help="override version, e.g. V1.0")
    p.add_argument("--owner", default=None, help="override copyright owner")
    p.add_argument("--date", default=None, help="override cover date, YYYY-MM-DD")
    p.add_argument("--title", default=None, help="cover subtitle, default 软件说明书")
    p.add_argument("--max-image-width-cm", type=float, default=15.5)
    p.add_argument("--max-image-height-cm", type=float, default=19.0)
    p.add_argument("--pdf-engine", default="auto", choices=["auto", "word", "libreoffice"],
                   help="pdf conversion backend, default auto")
    p.add_argument("--no-pdf", action="store_true", help="skip pdf conversion")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = Path(args.config).expanduser()
    if not config_path.exists():
        die("config not found: %s" % config_path)

    manual = load_config(config_path)
    if args.name:
        manual.name = args.name.strip()
    if args.version:
        manual.version = args.version.strip()
    if args.owner is not None:
        manual.owner = args.owner.strip()
    if args.date:
        manual.when = args.date.strip()
    if args.title:
        manual.title = args.title.strip()
    if not manual.name:
        die("software name is empty; pass --name or set it in the config")

    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    docx_path = out_dir / ("03_%s_%s.docx" % (manual.title, manual.version))
    pdf_path = out_dir / ("04_%s_%s.pdf" % (manual.title, manual.version))

    image_count = build_docx(manual, docx_path, config_path.parent,
                             args.max_image_width_cm, args.max_image_height_cm)
    print("[OK] docx: %s" % docx_path)
    print("[OK] sections: %d, images: %d" % (len(manual.sections), image_count))

    if args.no_pdf:
        print("[INFO] --no-pdf set, pdf export skipped")
        return 0

    engine = None
    if args.pdf_engine in ("auto", "word"):
        engine = export_pdf_word(docx_path, pdf_path)
        if engine is None:
            engine = export_pdf_word_powershell(docx_path, pdf_path)
    if engine is None and args.pdf_engine in ("auto", "libreoffice"):
        engine = export_pdf_libreoffice(docx_path, out_dir)
    if engine is None:
        warn("Microsoft Word COM and LibreOffice are both unavailable, docx kept only")
        print("[INFO] install LibreOffice or pywin32 to enable automatic pdf export")
        return 0

    if not pdf_path.exists():
        warn("pdf engine %s reported success but no pdf was produced" % engine)
        return 0
    pages = pdf_page_count(pdf_path)
    print("[OK] pdf : %s (%s, %d pages)" % (pdf_path, engine, pages))
    if pages and not (10 <= pages <= 25):
        warn("manual pages %d, CPCC recommends 10 to 25 pages" % pages)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
