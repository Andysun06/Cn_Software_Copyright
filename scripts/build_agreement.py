#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate a CPCC style cooperation development agreement (docx and pdf).

The agreement is used when two or more developers file a joint software
copyright application. It records the software identity, every owner name and
ID number, each owner's development scope, the ownership mode (joint tenancy
or shares), the nominated first owner, and a manual signature block.

Usage:
    python build_agreement.py --name "智能排课管理系统" --version V1.0 \
        --date 2025-11-18 --sharing "按份共有" \
        --owner "张三|110101199001011234|负责后端核心算法与数据库设计|60" \
        --owner "李四|310101199202022345|负责前端界面与交互实现|40" \
        --out-dir "软著材料"
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

ID_RE = re.compile(r"^\d{17}[\dXx]$|^\d{15}$")
BAD_NAME_RE = re.compile(r'[\\/:*?"<>|]')


@dataclass
class Owner:
    name: str
    id_number: str
    duty: str
    share: float | None = None
    order: int = 0


@dataclass
class Agreement:
    name: str
    version: str
    sign_date: str
    sharing: str
    owners: list[Owner] = field(default_factory=list)
    first_owner: str = ""
    software_type: str = "计算机软件"
    completed_date: str = ""


def die(msg: str) -> None:
    print("[ERROR] " + msg, file=sys.stderr)
    raise SystemExit(1)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build a cooperation development agreement docx and pdf.")
    p.add_argument("--name", required=True, help="software full name")
    p.add_argument("--version", default="V1.0", help="version, default V1.0")
    p.add_argument("--date", default=date.today().isoformat(), help="sign date, default today")
    p.add_argument("--sharing", required=True, choices=["共同共有", "按份共有"],
                   help="ownership mode")
    p.add_argument("--owner", action="append", required=True,
                   metavar="NAME|ID|DUTY|SHARE",
                   help="repeatable owner line, share required when 按份共有")
    p.add_argument("--first-owner", default=None, help="first owner name, default the first line")
    p.add_argument("--out-dir", default="软著材料", help="output directory")
    p.add_argument("--completed-date", default="", help="development completion date")
    return p.parse_args(argv)


def parse_owner(raw: str, index: int) -> Owner:
    parts = [x.strip() for x in raw.split("|")]
    while len(parts) < 4:
        parts.append("")
    name, id_number, duty, share_text = parts[:4]
    if not name:
        die("owner %d has an empty name" % index)
    if not ID_RE.match(id_number):
        die("owner %s has an invalid ID number: %s" % (name, id_number))
    if not duty:
        die("owner %s has an empty development duty" % name)
    share = None
    if share_text:
        text = share_text.rstrip("%").strip()
        try:
            share = float(text)
        except ValueError:
            die("owner %s has an invalid share: %s" % (name, share_text))
        if not (0 < share <= 100):
            die("owner %s share must be between 0 and 100" % name)
    return Owner(name=name, id_number=id_number, duty=duty, share=share, order=index)


def validate(agreement: Agreement) -> None:
    if len(agreement.owners) < 2:
        die("a cooperation agreement needs at least two owners")
    names = [o.name for o in agreement.owners]
    if len(set(names)) != len(names):
        die("duplicate owner names: " + ", ".join(names))
    if agreement.sharing == "按份共有":
        missing = [o.name for o in agreement.owners if o.share is None]
        if missing:
            die("shared ownership requires a share for every owner, missing: " + ", ".join(missing))
        total = round(sum(o.share or 0 for o in agreement.owners), 2)
        if abs(total - 100.0) > 0.01:
            die("share total must equal 100%%, got %s%%" % total)
    if agreement.first_owner and agreement.first_owner not in names:
        die("first owner %s is not in the owner list" % agreement.first_owner)
    if not agreement.first_owner:
        agreement.first_owner = names[0]


def share_text(owner: Owner, sharing: str) -> str:
    if sharing == "按份共有" and owner.share is not None:
        return "%g%%" % owner.share
    return "共同共有"


def clause_blocks(a: Agreement) -> list[tuple[str, str]]:
    names = "、".join(o.name for o in a.owners)
    sharing_line = (
        "各方按下列比例按份享有本软件著作权: "
        + "; ".join("%s %s" % (o.name, share_text(o, a.sharing)) for o in a.owners)
        + "。"
        if a.sharing == "按份共有"
        else "本软件著作权由全体合作开发者共同共有, 行使著作权时须经全体一致同意。"
    )
    return [
        ("第一条 软件基本信息",
         "本协议标的软件名称为《%s》, 版本号为 %s, 开发完成日期为 %s。"
         "该软件由全体合作开发者共同参与完成, 属于合作开发作品。"
         % (a.name, a.version, a.completed_date or "见申请表")),
        ("第二条 合作开发者与开发分工",
         "本软件的合作开发者共 %d 人, 按申请表排名顺序为: %s。"
         "各方的具体开发分工见本协议所附合作开发者信息表, 各方确认该分工真实反映实际投入。"
         % (len(a.owners), names)),
        ("第三条 权利归属",
         "经全体合作开发者协商一致, 本软件著作权的归属方式为%s。%s"
         % (a.sharing, sharing_line)),
        ("第四条 共同代表人",
         "全体合作开发者一致推举 %s 作为共同代表人, 负责办理本软件著作权登记申请、"
         "补正答复、证书领取及相关文件的签署。共同代表人不得处分本软件著作权, "
         "涉及权利转让、许可或质押的事项须经全体合作开发者书面同意。"
         % a.first_owner),
        ("第五条 权利与义务",
         "各方保证本软件为原创成果, 不侵犯任何第三方的著作权、专利权、商标权或商业秘密。"
         "各方对其提交的代码、素材、文档的真实性与合法性负责。"
         "因一方提供的内容引发第三方主张权利的, 由该方承担相应责任。"),
        ("第六条 保密与争议解决",
         "各方对在合作开发过程中知悉的源代码、技术方案与商业信息负有保密义务, "
         "未经全体书面同意不得向第三方披露。因本协议产生的争议, 各方应先行协商; "
         "协商不成的, 提交共同代表人所在地有管辖权的人民法院处理。"),
        ("第七条 协议生效与份数",
         "本协议自全体合作开发者签字之日起生效, 一式 %d 份, 每位合作开发者各执一份, "
         "提交登记机关一份, 具有同等法律效力。本协议未尽事宜由各方另行书面约定。"
         % (len(a.owners) + 1)),
    ]


# --------------------------------------------------------------------------
# docx output
# --------------------------------------------------------------------------

def build_docx(a: Agreement, out_path: Path) -> None:
    try:
        import docx
        from docx.enum.table import WD_TABLE_ALIGNMENT
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.shared import Cm, Pt
    except ImportError:
        die("python-docx is required: pip install python-docx")

    doc = docx.Document()
    section = doc.sections[0]
    section.top_margin = Cm(2.4)
    section.bottom_margin = Cm(2.2)
    section.left_margin = Cm(2.6)
    section.right_margin = Cm(2.4)

    style = doc.styles["Normal"]
    style.font.name = "宋体"
    style.font.size = Pt(10.5)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("合作开发协议")
    run.font.name = "黑体"
    run.element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
    run.font.size = Pt(20)
    run.bold = True

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_run = sub.add_run(a.name + " " + a.version)
    sub_run.font.size = Pt(12)

    intro = doc.add_paragraph(
        "本协议由下列合作开发者就共同开发的《%s》%s 软件著作权归属及相关事项, "
        "依据《中华人民共和国著作权法》与《计算机软件保护条例》协商订立。"
        % (a.name, a.version))
    intro.paragraph_format.first_line_indent = Pt(21)

    for heading, body in clause_blocks(a):
        h = doc.add_paragraph()
        h_run = h.add_run(heading)
        h_run.font.name = "黑体"
        h_run.element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
        h_run.font.size = Pt(11.5)
        h_run.bold = True
        para = doc.add_paragraph(body)
        para.paragraph_format.first_line_indent = Pt(21)
        para.paragraph_format.space_after = Pt(4)

    doc.add_paragraph("")
    info_head = doc.add_paragraph()
    info_run = info_head.add_run("合作开发者信息表")
    info_run.bold = True
    info_run.font.size = Pt(11.5)

    table = doc.add_table(rows=1, cols=5)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    widths = [Cm(1.2), Cm(2.8), Cm(5.6), Cm(5.2), Cm(2.2)]
    headers = ["序号", "姓名", "身份证号", "开发分工", "权利份额"]
    for cell, text, width in zip(table.rows[0].cells, headers, widths):
        cell.width = width
        cell.text = ""
        run = cell.paragraphs[0].add_run(text)
        run.bold = True
        run.font.size = Pt(10)
    for owner in a.owners:
        cells = table.add_row().cells
        values = [str(owner.order), owner.name, owner.id_number, owner.duty,
                  share_text(owner, a.sharing)]
        for cell, text, width in zip(cells, values, widths):
            cell.width = width
            cell.text = ""
            run = cell.paragraphs[0].add_run(text)
            run.font.size = Pt(9.5)

    doc.add_paragraph("")
    sign_head = doc.add_paragraph()
    sign_run = sign_head.add_run("全体合作开发者签字")
    sign_run.bold = True
    sign_run.font.size = Pt(11.5)

    sign_table = doc.add_table(rows=1, cols=4)
    sign_table.style = "Table Grid"
    sign_headers = ["序号", "姓名", "手写签名", "签字日期"]
    for cell, text in zip(sign_table.rows[0].cells, sign_headers):
        cell.text = ""
        run = cell.paragraphs[0].add_run(text)
        run.bold = True
        run.font.size = Pt(10)
    for owner in a.owners:
        cells = sign_table.add_row().cells
        for cell, text in zip(cells, [str(owner.order), owner.name, "", ""]):
            cell.text = ""
            run = cell.paragraphs[0].add_run(text)
            run.font.size = Pt(10)
        for cell in cells[2:]:
            cell.paragraphs[0].add_run("\n\n")

    doc.add_paragraph("")
    note = doc.add_paragraph("说明: 请全体合作开发者使用黑色签字笔亲笔签名并手写日期, "
                             "签名须与身份证姓名一致, 不得代签或打印签名。")
    note.runs[0].font.size = Pt(9)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))


# --------------------------------------------------------------------------
# pdf output
# --------------------------------------------------------------------------

def register_cjk() -> tuple[str, str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        (r"C:/Windows/Fonts/msyh.ttc", 0),
        (r"C:/Windows/Fonts/simhei.ttf", 0),
        (r"C:/Windows/Fonts/simsun.ttc", 0),
        (r"C:/Windows/Fonts/Deng.ttf", 0),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
        ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0),
    ]
    regular = bold = None
    for path, index in candidates:
        if not Path(path).exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont("AgreeCJK", path, subfontIndex=index))
            regular = "AgreeCJK"
            break
        except Exception:  # noqa: BLE001
            continue
    if regular is None:
        die("no CJK font found for pdf output")
    for path, index in [(r"C:/Windows/Fonts/msyhbd.ttc", 0),
                        (r"C:/Windows/Fonts/simhei.ttf", 0)]:
        if not Path(path).exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont("AgreeCJKBold", path, subfontIndex=index))
            bold = "AgreeCJKBold"
            break
        except Exception:  # noqa: BLE001
            continue
    return regular, bold or regular


def build_pdf(a: Agreement, out_path: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate,
                                    Spacer, Table, TableStyle)

    regular, bold = register_cjk()
    styles = {
        "title": ParagraphStyle("title", fontName=bold, fontSize=20, leading=30,
                                alignment=TA_CENTER, spaceAfter=6),
        "sub": ParagraphStyle("sub", fontName=regular, fontSize=12, leading=20,
                              alignment=TA_CENTER, spaceAfter=18),
        "h": ParagraphStyle("h", fontName=bold, fontSize=11.5, leading=20,
                            spaceBefore=10, spaceAfter=4),
        "body": ParagraphStyle("body", fontName=regular, fontSize=10.5, leading=19,
                               alignment=TA_LEFT, firstLineIndent=21, wordWrap="CJK"),
        "cell": ParagraphStyle("cell", fontName=regular, fontSize=9, leading=13),
        "note": ParagraphStyle("note", fontName=regular, fontSize=8.5, leading=13,
                               textColor=colors.HexColor("#444444")),
    }

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont(regular, 8.5)
        canvas.setFillColor(colors.HexColor("#555555"))
        canvas.drawCentredString(A4[0] / 2.0, 1.5 * cm,
                                 "第 %d 页 / 共 %d 页" % (doc.page, total_pages[0]))
        canvas.restoreState()

    total_pages = [1]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                            leftMargin=2.5 * cm, rightMargin=2.3 * cm,
                            topMargin=2.3 * cm, bottomMargin=2.2 * cm,
                            title="合作开发协议-" + a.name)
    story = [Paragraph("合作开发协议", styles["title"]),
             Paragraph(a.name + " " + a.version, styles["sub"]),
             Paragraph("本协议由下列合作开发者就共同开发的《%s》%s 软件著作权归属及相关事项, "
                       "依据《中华人民共和国著作权法》与《计算机软件保护条例》协商订立。"
                       % (a.name, a.version), styles["body"]),
             Spacer(1, 6)]

    for heading, body in clause_blocks(a):
        story.append(Paragraph(heading, styles["h"]))
        story.append(Paragraph(body, styles["body"]))

    story.append(Spacer(1, 12))
    story.append(Paragraph("合作开发者信息表", styles["h"]))

    data = [[Paragraph(x, styles["cell"]) for x in ["序号", "姓名", "身份证号", "开发分工", "权利份额"]]]
    for owner in a.owners:
        data.append([Paragraph(x, styles["cell"]) for x in [
            str(owner.order), owner.name, owner.id_number, owner.duty,
            share_text(owner, a.sharing)]])
    table = Table(data, colWidths=[1.2 * cm, 2.6 * cm, 4.6 * cm, 5.0 * cm, 2.0 * cm],
                  repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#666666")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFEFEF")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(table)

    story.append(Spacer(1, 18))
    story.append(Paragraph("全体合作开发者签字", styles["h"]))
    story.append(Spacer(1, 8))
    sign = [[Paragraph(x, styles["cell"]) for x in ["序号", "姓名", "手写签名", "签字日期"]]]
    for owner in a.owners:
        sign.append([Paragraph(str(owner.order), styles["cell"]),
                     Paragraph(owner.name, styles["cell"]),
                     Paragraph("", styles["cell"]),
                     Paragraph("", styles["cell"])])
    sign_table = Table(sign, colWidths=[1.4 * cm, 3.4 * cm, 6.4 * cm, 3.6 * cm],
                       rowHeights=[0.9 * cm] + [1.7 * cm] * len(a.owners))
    sign_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#666666")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFEFEF")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(sign_table)
    story.append(Spacer(1, 14))
    story.append(Paragraph("说明: 请全体合作开发者使用黑色签字笔亲笔签名并手写日期, "
                           "签名须与身份证姓名一致, 不得代签或打印签名。", styles["note"]))
    story.append(Spacer(1, 18))
    story.append(Paragraph("签署日期: %s" % a.sign_date, styles["body"]))

    # First pass counts pages, second pass writes the real total into the footer.
    import copy

    tmp_path = out_path.with_name(out_path.stem + ".tmp.pdf")
    doc_tmp = SimpleDocTemplate(str(tmp_path), pagesize=A4,
                                leftMargin=2.5 * cm, rightMargin=2.3 * cm,
                                topMargin=2.3 * cm, bottomMargin=2.2 * cm,
                                title="合作开发协议-" + a.name)
    story_backup = copy.deepcopy(story)
    doc_tmp.build(story, onFirstPage=on_page, onLaterPages=on_page)
    total_pages[0] = max(1, doc_tmp.page)
    doc.build(story_backup, onFirstPage=on_page, onLaterPages=on_page)
    if tmp_path.exists():
        tmp_path.unlink()


def build(a: Agreement, out_dir: Path) -> tuple[Path, Path]:
    safe_name = BAD_NAME_RE.sub("_", a.name)
    stem = "合作开发协议-%s%s" % (safe_name, a.version)
    docx_path = out_dir / (stem + ".docx")
    pdf_path = out_dir / (stem + ".pdf")
    build_docx(a, docx_path)
    build_pdf(a, pdf_path)
    return docx_path, pdf_path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    owners = [parse_owner(raw, idx) for idx, raw in enumerate(args.owner, start=1)]
    agreement = Agreement(
        name=args.name.strip(),
        version=args.version.strip(),
        sign_date=args.date.strip(),
        sharing=args.sharing,
        owners=owners,
        first_owner=(args.first_owner or "").strip(),
        completed_date=args.completed_date.strip(),
    )
    if not agreement.name:
        die("software name is empty")
    validate(agreement)

    out_dir = Path(args.out_dir).expanduser()
    docx_path, pdf_path = build(agreement, out_dir)
    print("[OK] docx: %s" % docx_path)
    print("[OK] pdf : %s" % pdf_path)
    print("[OK] owners: %d, sharing: %s" % (len(owners), agreement.sharing))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
