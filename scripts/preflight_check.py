#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Preflight checker for CPCC software copyright application packages.

It validates every material class that must agree with each other:

  1. application form (docx / xlsx / md / txt)
  2. functional description text (500 to 1300 Chinese characters)
  3. software manual (docx / pdf / md)
  4. 60 page source code PDF with centered header and right aligned footer
  5. interface screenshots, with an extra game checklist
  6. cooperation agreement, owner order and share percentages

Checks cover: four way name and version consistency, owner order, share sum,
cooperation agreement presence, BOM residue, personal debug strings, functional
description length, placeholder and sensitive word residue, source PDF page and
line counts, glyph corruption, special symbol retention, manual sparse pages,
screenshot resolution and scene coverage, game screenshot checklist, and AI
traces inside the source tree.

Exit code 0 means no ERROR. With --strict, warnings also fail the run.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path

# --------------------------------------------------------------------------
# constants
# --------------------------------------------------------------------------

CODE_EXTS = {
    ".py", ".java", ".kt", ".go", ".rs", ".c", ".h", ".cc", ".cpp", ".cxx",
    ".hpp", ".hh", ".cs", ".php", ".rb", ".scala", ".swift", ".m", ".mm",
    ".sql", ".lua", ".pl", ".r", ".jl", ".dart", ".js", ".jsx", ".mjs",
    ".cjs", ".ts", ".tsx", ".vue", ".svelte", ".html", ".htm", ".css",
    ".scss", ".sass", ".less", ".wxml", ".wxss", ".axml", ".acss", ".ejs",
    ".hbs", ".pug", ".jsp", ".ftl", ".tpl", ".qml", ".xaml",
}

SKIP_DIRS = {
    ".git", ".svn", ".idea", ".vscode", "node_modules", "vendor", "dist",
    "build", "out", "target", "obj", "coverage", ".next", ".nuxt", ".output",
    ".venv", "venv", "env", "__pycache__", ".pytest_cache", ".gradle", ".mvn",
    "site-packages", "dist-packages", ".cache", "logs", "tmp", "temp",
    "skills", "cn_software_copyright", "软著材料",
}

ARTIFACT_SKIP_DIRS = SKIP_DIRS - {"软著材料"}

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}

SHOT_DIR_NAMES = ["截图", "界面截图", "screenshots", "screenshot", "shots", "images", "figures"]

PLACEHOLDER_PATTERNS = [
    ("待填写标记", r"\[待填写\]|\[待补充\]|\[请填写\]|\[请输入\]|【待[^】]{0,8}】"),
    ("TODO/TBD 标记", r"\bTODO\b|\bTBD\b|\bFIXME\b"),
    ("占位符 XXX", r"(?<![A-Za-z])(?:XXX+|××+|＊＊+|\?\?\?)(?![A-Za-z])"),
    ("示例占位文本", r"Lorem ipsum|示例文本|此处填写|待定|待确认|请输入您的"),
]

AI_TEXT_PATTERNS = [
    ("AI 生成痕迹", r"作为一个\s*AI|作为AI|AI\s*生成|由\s*AI\s*撰写|大模型生成|语言模型生成"),
    ("AI 产品名", r"ChatGPT|OpenAI|Claude|GPT-[0-9]|Copilot|DeepSeek"),
]

AD_WORDS = r"国家级|世界级|最高级|最佳产品|第一品牌|唯一指定|绝无仅有"
CLICHE_WORDS = r"界面美观大方|操作简单易懂|性能卓越|功能强大|用户体验良好|方便快捷|易于上手"

VERSION_MODIFIER = r"轻量版|专业版|旗舰版|测试版|试用版|体验版|精简版|\bLite\b|\bPro\b|\bBeta\b|\bDemo\b"

SCENE_GROUPS = {
    "启动或登录": r"启动|登录|欢迎|首页",
    "主工作台": r"主界面|工作台|主页|仪表盘|概览",
    "核心功能": r"新增|编辑|查询|导入|处理|计算|生成|排课|下单",
    "参数配置": r"配置|设置|参数|选项|偏好",
    "导出或报告": r"导出|报告|统计|报表|打印",
}

GAME_HINTS = r"游戏软件|网络游戏|手机游戏|单机游戏|客户端游戏|游戏类型|卡牌|关卡|副本|战斗系统|角色养成"

GAME_SHOT_GROUPS = {
    "健康游戏忠告": r"健康游戏忠告",
    "游戏主界面": r"主界面|主菜单|游戏首页|游戏大厅",
    "角色或卡牌展示": r"角色|卡牌|将领|英雄|武将|精灵|立绘",
    "可进入场景": r"世界地图|地图|战斗|会战|副本|关卡|场景",
    "可体验系统": r"背包|商店|任务|技能|排行|招募|锻造|合成",
    "通关闭环": r"通关|结算|胜利|失败|存档|退出|毕业",
}

GAME_REQUIRED = {"健康游戏忠告", "角色或卡牌展示", "通关闭环"}

DEBUG_PATTERNS = [
    ("测试口令", r"测试口令|调试口令|万能密码|默认密码|管理员密码"),
    ("后门标记", r"backdoor|easter[_ ]?egg|god[_ ]?mode|super[_ ]?password"),
    ("调试开关", r"debug\s*[:=]\s*(true|1)\b|DEBUG\s*=\s*True"),
    ("硬编码凭据", r"(?i)(password|passwd|pwd)\s*[:=]\s*[\"'][^\"']{3,}[\"']"),
    ("彩蛋提示", r"彩蛋|隐藏关卡|秘籍|输入口令|测试后门"),
]

BOM_BYTES = b"\xef\xbb\xbf"

OWNER_LABEL = r"(?:著作权人|著作权所有人|软件权利人|申请人)"

FIELD_LABELS = re.compile(
    r"^\s*(软件全称|软件名称|软件简称|软件类型|版本号|开发完成日期|首次发表|著作权人|"
    r"权利取得方式|开发方式|软件分类|硬件环境|软件环境|编程语言|源程序量|"
    r"开发分工|权利归属|共有方式|主要功能|技术特点|适用范围|开发硬件|运行硬件|"
    r"运行环境|开发环境)\s*[:：|]"
)

SOURCE_PROBES = [
    ("__future__", r"__future__"),
    ("查询管道", r"\|"),
    ("大于等于", r">="),
    ("小于等于", r"<="),
    ("不等于", r"!="),
    ("装饰器", r"@"),
    ("星号", r"\*"),
]

NAME_LABELS = r"(?:软件全称|软件名称|软件名|全称)"
VERSION_LABELS = r"(?:版本号|版本|Version|Ver)"


# --------------------------------------------------------------------------
# result model
# --------------------------------------------------------------------------

@dataclass
class Finding:
    check: str
    level: str          # ERROR / WARN / INFO
    title: str
    detail: str = ""
    where: str = ""

    def __str__(self) -> str:
        loc = ("  @ " + self.where) if self.where else ""
        body = ("  " + self.detail) if self.detail else ""
        return "[%s] %s %s%s%s" % (self.level, self.check, self.title, loc, body)


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    def add(self, check: str, level: str, title: str, detail: str = "", where: str = "") -> None:
        self.findings.append(Finding(check, level, title, detail, where))

    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "ERROR"]

    def warns(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "WARN"]

    def has(self, check: str) -> bool:
        return any(f.check == check for f in self.findings)


# --------------------------------------------------------------------------
# text and pdf helpers
# --------------------------------------------------------------------------

def read_plain(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030", "utf-16", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def read_docx(path: Path) -> str:
    try:
        import docx  # type: ignore
        doc = docx.Document(str(path))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text.replace("\n", " ") for cell in row.cells))
        return "\n".join(parts)
    except Exception:  # noqa: BLE001
        pass
    try:
        import zipfile
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", errors="replace")
        xml = xml.replace("</w:p>", "\n").replace("</w:tc>", " | ")
        text = re.sub(r"<[^>]+>", "", xml)
        import html
        return html.unescape(text)
    except Exception:  # noqa: BLE001
        return ""


def read_xlsx(path: Path) -> str:
    try:
        import openpyxl  # type: ignore
        wb = openpyxl.load_workbook(str(path), data_only=True)
        rows = []
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) for c in row if c is not None]
                if cells:
                    rows.append(" | ".join(cells))
        return "\n".join(rows)
    except Exception:  # noqa: BLE001
        return ""


def read_pdf_pages(path: Path) -> list[str]:
    try:
        import fitz  # type: ignore
        with fitz.open(str(path)) as doc:
            return [page.get_text("text") for page in doc]
    except Exception:  # noqa: BLE001
        pass
    try:
        from pypdf import PdfReader  # type: ignore
        reader = PdfReader(str(path))
        return [(p.extract_text() or "") for p in reader.pages]
    except Exception:  # noqa: BLE001
        return []


def read_any(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return read_docx(path)
    if suffix == ".xlsx":
        return read_xlsx(path)
    if suffix == ".pdf":
        return "\n".join(read_pdf_pages(path))
    if suffix in {".md", ".txt", ".csv"}:
        return read_plain(path)
    return read_plain(path)


def image_size(path: Path) -> tuple[int, int]:
    try:
        with path.open("rb") as fh:
            data = fh.read(131072)
    except OSError:
        return (0, 0)
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h = struct.unpack(">H", data[i + 5:i + 7])[0]
                w = struct.unpack(">H", data[i + 7:i + 9])[0]
                return (w, h)
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seg = struct.unpack(">H", data[i + 2:i + 4])[0]
            i += 2 + seg
    return (0, 0)


def norm_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = re.sub(r"\s+", "", value)
    return value.strip("“”\"'《》〈〉<>【】[]()（）:：,，。.;；")


def norm_version(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").upper()
    value = re.sub(r"\s+", "", value)
    value = value.lstrip("V")
    value = re.sub(r"[^0-9.]", "", value)
    return value.strip(".")


def cjk_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text or ""))


def collect_names(text: str) -> list[str]:
    found = []
    pattern = NAME_LABELS + r"\s*[:：|]*\s*([^\n\r|]{2,40})"
    for match in re.finditer(pattern, text or ""):
        raw = match.group(1).strip()
        raw = re.split(r"\s{3,}|[，,；;。]", raw)[0]
        value = norm_name(raw)
        if 2 <= len(value) <= 40:
            found.append(value)
    return found


def collect_versions(text: str) -> list[str]:
    found = []
    pattern = VERSION_LABELS + r"\s*[:：|]*\s*(V?\d+(?:\.\d+){0,3})"
    for match in re.finditer(pattern, text or "", re.IGNORECASE):
        value = norm_version(match.group(1))
        if value:
            found.append(value)
    return found


def majority(values: list[str]) -> str | None:
    if not values:
        return None
    counts: dict[str, int] = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def extract_owners(text: str) -> list[str]:
    """Return owner names in declared order, with IDs and notes removed."""
    match = re.search(OWNER_LABEL + r"\s*[:：|]*\s*([^\n\r]{2,240})", text or "")
    if not match:
        return []
    raw = match.group(1)
    raw = re.split(r"(?:开发方式|权利取得|共有方式|软件分类|版本号|开发完成)", raw)[0]
    raw = re.sub(r"[（(][^）)]*身份证[^）)]*[）)]", "", raw)
    raw = re.sub(r"身份证号?\s*[:：]?\s*\d{15,18}[\dXx]?", "", raw)
    owners: list[str] = []
    for token in re.split(r"[、,，;；/]+", raw):
        token = re.sub(r"\d{17}[\dXx]|\d{15}", "", token)
        token = re.sub(r"[（(].*?[）)]", "", token)
        token = token.strip(" 　:：|")
        if 1 <= len(token) <= 30 and not re.search(r"^(无|暂无|个人|单位|公司|同上)$", token):
            owners.append(token)
    return owners


def extract_dev_mode(text: str) -> str | None:
    match = re.search(r"开发方式\s*[:：|]*\s*(独立开发|合作开发)", text or "")
    return match.group(1) if match else None


def extract_sharing(text: str) -> str | None:
    match = re.search(r"(共同共有|按份共有)", text or "")
    return match.group(1) if match else None


def extract_shares(text: str) -> list[int]:
    return [int(x) for x in re.findall(r"(\d{1,3}(?:\.\d+)?)\s*%", text or "")]


def split_share_numbers(text: str) -> list[float]:
    return [float(x) for x in re.findall(r"(\d{1,3}(?:\.\d+)?)\s*%", text or "")]


def is_game_software(text: str, mode: str) -> bool:
    if mode == "game":
        return True
    if mode == "general":
        return False
    return bool(re.search(GAME_HINTS, text or ""))


def bom_paths(project: Path) -> list[str]:
    bad: list[str] = []
    exts = CODE_EXTS | {".txt", ".md", ".csv", ".json", ".html", ".xml", ".csv"}
    for path in project.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in exts:
            continue
        rel = path.relative_to(project)
        if any(p.lower() in SKIP_DIRS or p.startswith(".") for p in rel.parts[:-1]):
            continue
        try:
            with path.open("rb") as fh:
                if fh.read(3) == BOM_BYTES:
                    bad.append(rel.as_posix())
        except OSError:
            continue
    return bad


# --------------------------------------------------------------------------
# discovery
# --------------------------------------------------------------------------

def find_artifacts(project: Path) -> tuple[Path | None, Path | None, Path | None, Path | None]:
    files = []
    for path in project.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = [p.lower() for p in path.relative_to(project).parts[:-1]]
        if any(p in ARTIFACT_SKIP_DIRS or p.startswith(".") for p in rel_parts):
            continue
        if path.suffix.lower() in {".py", ".js", ".ts", ".cpp", ".java", ".cs"}:
            continue
        files.append(path)

    def pick(keywords: list[str], exts: set[str]) -> Path | None:
        scored: list[tuple[int, int, Path]] = []
        for p in files:
            name = p.name.lower()
            stem = p.stem.lower()
            if p.suffix.lower() not in exts:
                continue
            if any(k.lower() in stem for k in keywords):
                in_package = 1 if "软著" in p.as_posix() else 0
                scored.append((in_package, -len(stem), p))
        if not scored:
            return None
        scored.sort(key=lambda x: (-x[0], -x[1], str(x[2])))
        return scored[0][2]

    application = pick(["申请表", "申请信息", "登记表", "基本信息"], {".docx", ".xlsx", ".md", ".txt"})
    manual = pick(["说明书", "操作手册", "用户手册", "使用说明"], {".docx", ".pdf", ".md"})
    source_pdf = pick(["源代码", "源程序", "源码"], {".pdf"})

    shots = None
    best = 0
    for path in project.rglob("*"):
        if path.is_dir() and any(k in path.name.lower() for k in SHOT_DIR_NAMES):
            count = sum(1 for p in path.rglob("*") if p.suffix.lower() in IMAGE_EXTS)
            if count > best:
                best, shots = count, path
    return application, manual, source_pdf, shots


def find_extras(project: Path) -> dict:
    extras = {"feature": None, "agreement_docx": None, "agreement_pdf": None, "guide": None}
    for path in project.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(project)
        if any(p.lower() in ARTIFACT_SKIP_DIRS or p.startswith(".") for p in rel.parts[:-1]):
            continue
        stem = path.stem
        suffix = path.suffix.lower()
        in_package = "软著" in rel.as_posix()
        if suffix == ".txt" and ("主要功能" in stem or "技术特点" in stem):
            if extras["feature"] is None or in_package:
                extras["feature"] = path
        elif suffix == ".docx" and "合作开发协议" in stem:
            extras["agreement_docx"] = path
        elif suffix == ".pdf" and "合作开发协议" in stem:
            extras["agreement_pdf"] = path
        elif suffix == ".md" and ("提交流程" in stem or "签章" in stem):
            extras["guide"] = path
    return extras


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------

def check_artifacts(report: Report, app, manual, src_pdf, shots) -> None:
    for label, path in [("申请表", app), ("软件说明书", manual),
                        ("源代码 PDF", src_pdf), ("截图目录", shots)]:
        if path is None:
            report.add("C01", "ERROR", "缺少交付物: " + label,
                       "未在项目内找到对应文件")
        else:
            report.add("C01", "INFO", "已找到" + label, "", str(path))


def check_consistency(report: Report, ctx: dict) -> None:
    app_names = collect_names(ctx["app_text"])
    manual_head = "\n".join(ctx["manual_text"].splitlines()[:40])
    manual_names = collect_names(ctx["manual_text"])[:30] + collect_names(manual_head)
    pdf_header = ""
    if ctx["source_pages"]:
        pdf_header = ctx["source_pages"][0].splitlines()[0] if ctx["source_pages"][0] else ""

    expected_name = ctx["expected_name"] or majority(app_names + manual_names)
    if not expected_name:
        report.add("C02", "ERROR", "无法提取软件全称",
                   "申请表与说明书均未出现 软件全称/软件名称 字段")
        return

    report.add("C02", "INFO", "软件全称基准值: " + expected_name)
    if app_names and norm_name(app_names[0]) != expected_name:
        report.add("C02", "ERROR", "申请表名称与基准值不一致: " + app_names[0], "", str(ctx["application"]))
    manual_flat = norm_name(ctx["manual_text"][:20000])
    if expected_name not in manual_flat:
        report.add("C02", "ERROR", "说明书未出现基准名称: " + expected_name,
                   "检测到: " + (", ".join(sorted(set(manual_names))[:5]) or "无"),
                   str(ctx["manual"]))
    else:
        report.add("C02", "INFO", "说明书名称匹配")
    if pdf_header:
        parts = [x for x in re.split(r"\s{2,}", pdf_header.strip()) if x]
        if expected_name not in norm_name(pdf_header):
            report.add("C02", "ERROR", "源代码 PDF 页眉未包含基准名称: " + pdf_header, "", "page 1")
        else:
            report.add("C02", "INFO", "源代码 PDF 页眉名称匹配", "", "page 1")

    app_versions = collect_versions(ctx["app_text"])
    manual_versions = collect_versions(ctx["manual_text"])
    if not manual_versions:
        manual_versions = [norm_version(m) for m in
                           re.findall(r"\bV\d+(?:\.\d+){1,3}\b", ctx["manual_text"][:20000])]
    pdf_versions = []
    if pdf_header:
        for token in re.findall(r"V?\d+(?:\.\d+){1,3}", pdf_header, re.IGNORECASE):
            pdf_versions.append(norm_version(token))
    expected_version_raw = ctx["expected_version"]
    expected_version = norm_version(expected_version_raw) if expected_version_raw else majority(app_versions + manual_versions)
    if not expected_version:
        report.add("C03", "ERROR", "无法提取版本号", "材料中未出现 版本号 字段")
        return
    report.add("C03", "INFO", "版本号基准值: V" + expected_version)

    for label, values, where in [
        ("申请表", app_versions, ctx["application"]),
        ("说明书", manual_versions, ctx["manual"]),
        ("源代码 PDF", pdf_versions, ctx["source_pdf"]),
    ]:
        if not values:
            report.add("C03", "WARN", "未能从" + label + "提取版本号", "请人工核对", str(where or ""))
            continue
        bad = sorted({v for v in values if v != expected_version})
        if bad:
            report.add("C03", "ERROR",
                       "%s版本号不一致: %s, 应为 V%s" % (label, ", ".join(bad), expected_version),
                       "", str(where or ""))
        else:
            report.add("C03", "INFO", label + "版本号匹配", "", str(where or ""))

    if ctx["shots"]:
        report.add("C04", "WARN", "截图中的软件名称与版本号需人工确认",
                   "截图目录: %s, 共 %d 张" % (ctx["shots"], ctx["shot_count"]))


def check_dates(report: Report, ctx: dict) -> None:
    text = ctx["app_text"]
    match = re.search(r"开发完成日期\s*[:：|]*\s*(\d{4})\s*[-年./]\s*(\d{1,2})\s*[-月./]\s*(\d{1,2})", text)
    if not match:
        report.add("C05", "WARN", "未找到开发完成日期", "申请表需明确开发完成日期")
        return
    try:
        done = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        report.add("C05", "ERROR", "开发完成日期不是合法日期: " + match.group(0))
        return
    if done > date.today():
        report.add("C05", "ERROR", "开发完成日期晚于今天: " + done.isoformat())
    else:
        report.add("C05", "INFO", "开发完成日期: " + done.isoformat())

    for label, pattern in [
        ("截图日期", r"截图日期\s*[:：|]*\s*(\d{4})\s*[-年./]\s*(\d{1,2})\s*[-月./]\s*(\d{1,2})"),
        ("报告日期", r"报告日期\s*[:：|]*\s*(\d{4})\s*[-年./]\s*(\d{1,2})\s*[-月./]\s*(\d{1,2})"),
    ]:
        for m in re.finditer(pattern, ctx["manual_text"] + "\n" + text):
            try:
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                continue
            if d > done:
                report.add("C05", "ERROR", label + "晚于开发完成日期: " + d.isoformat(),
                           "完成日期 " + done.isoformat())


def extract_description(text: str) -> str:
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.search(r"(主要功能|功能描述|软件功能|功能简介|功能说明)", line):
            start = i
            break
    if start is None:
        return ""
    collected = [lines[start]]
    for line in lines[start + 1:]:
        if FIELD_LABELS.match(line) and not re.search(r"(功能描述|主要功能|功能简介)", line):
            break
        collected.append(line)
        if len("\n".join(collected)) > 8000:
            break
    return "\n".join(collected)


def check_description(report: Report, ctx: dict, lo: int, hi: int) -> None:
    section = extract_description(ctx["app_text"])
    if not section:
        report.add("C06", "ERROR", "未找到功能描述段落", "申请表中需有 主要功能/功能描述 字段")
        return
    count = cjk_count(section)
    level = "INFO" if lo <= count <= hi else "ERROR"
    report.add("C06", level, "功能描述汉字数: %d, 要求 %d 到 %d" % (count, lo, hi))
    if count < 500:
        report.add("C06", "ERROR", "功能描述过短", "补充架构、模块、算法与环境四部分")
    elif count > 1300:
        report.add("C06", "ERROR", "功能描述过长", "压缩到 1300 字以内, 保留量化细节")

    groups = {
        "研发背景": r"现有|传统|人工|手工|效率|痛点|问题|背景",
        "分层架构": r"架构|分层|表现层|业务层|数据层|前后端|微服务",
        "功能模块": r"模块|子系统|功能点|组件",
        "算法结构": r"算法|公式|索引|数据结构|状态机|缓存|阈值|队列|哈希",
        "运行环境": r"运行环境|操作系统|Windows|Linux|内存|处理器|浏览器",
    }
    hit = [k for k, pat in groups.items() if re.search(pat, section)]
    if len(hit) < 5:
        missing = [k for k in groups if k not in hit]
        report.add("C07", "WARN", "功能描述五段结构不完整",
                   "缺少要素: " + ", ".join(missing))
    else:
        report.add("C07", "INFO", "功能描述五段结构齐备")

    paragraphs = [p for p in re.split(r"\n\s*\n", section) if cjk_count(p) >= 30]
    if len(paragraphs) < 5:
        report.add("C07", "WARN", "功能描述自然段偏少: %d 段" % len(paragraphs),
                   "建议按背景、架构、模块、算法、环境分为五段")


def scan_text(report: Report, label: str, text: str, where: str,
              placeholder_level: str = "ERROR") -> None:
    for name, pattern in PLACEHOLDER_PATTERNS:
        hits = re.findall(pattern, text or "")
        if hits:
            sample = ", ".join(sorted({h if isinstance(h, str) else str(h) for h in hits})[:5])
            report.add("C08", placeholder_level, "%s存在%s" % (label, name), "命中: " + sample, where)
    for name, pattern in AI_TEXT_PATTERNS:
        if re.search(pattern, text or "", re.IGNORECASE):
            report.add("C09", "ERROR", "%s存在%s" % (label, name), "", where)
    for match in re.finditer(AD_WORDS, text or ""):
        report.add("C10", "WARN", "%s存在广告法风险词: %s" % (label, match.group(0)), "", where)
    for match in re.finditer(CLICHE_WORDS, text or ""):
        report.add("C10", "WARN", "%s存在空洞套话: %s" % (label, match.group(0)),
                   "改写为可验证的具体能力", where)
    for match in re.finditer(VERSION_MODIFIER, text or ""):
        report.add("C11", "WARN", "%s出现版本修饰词: %s" % (label, match.group(0)),
                   "首次申请建议使用正式全称", where)


def check_source_pdf(report: Report, ctx: dict, pages_expected: int, lines_expected: int) -> None:
    pages = ctx["source_pages"]
    if not pages:
        report.add("C12", "ERROR", "源代码 PDF 无法读取或不存在", "", str(ctx["source_pdf"] or ""))
        return
    if len(pages) != pages_expected:
        report.add("C12", "ERROR", "源代码 PDF 页数为 %d, 应为 %d" % (len(pages), pages_expected),
                   "", str(ctx["source_pdf"]))

    header_re = re.compile(r"第\s*\d+\s*页|共\s*\d+\s*页")
    footer_re = re.compile(r"第\s*(\d+)\s*页\s*/\s*共\s*(\d+)\s*页")
    bad_pages = []
    header_bad = []
    footer_bad = []
    mojibake = []
    counts = ctx["page_line_counts"]
    expected_header = ""
    if ctx["expected_name"] and ctx["expected_version"]:
        expected_header = norm_name("%s %s" % (ctx["expected_name"], ctx["expected_version"]))
    for idx, text in enumerate(pages, start=1):
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if not lines:
            bad_pages.append((idx, 0))
            continue
        count = counts.get(idx)
        if count is None:
            count = len([ln for ln in lines if not header_re.search(ln)])
            if idx == 1 and count > lines_expected:
                count -= 1
        if count != lines_expected:
            bad_pages.append((idx, count))
        first = lines[0]
        if expected_header and norm_name(first) != expected_header:
            if ctx["expected_name"] and norm_name(ctx["expected_name"]) not in norm_name(first):
                header_bad.append((idx, first[:40]))
            else:
                header_bad.append((idx, "页眉格式不是 名称+版本: " + first[:40]))
        footer_match = footer_re.search(lines[-1]) if lines else None
        if not footer_match or int(footer_match.group(1)) != idx or int(footer_match.group(2)) != len(pages):
            footer_bad.append((idx, lines[-1][:40] if lines else ""))
        if "锟斤拷" in text or "\ufffd" in text or "\ufeff" in text:
            mojibake.append(idx)

    if bad_pages:
        sample = ", ".join("p%d=%d行" % (p, c) for p, c in bad_pages[:8])
        report.add("C13", "ERROR", "源代码每页行数不是 %d: %d 页异常" % (lines_expected, len(bad_pages)),
                   sample)
    else:
        report.add("C13", "INFO", "源代码每页 %d 行, 共 %d 页" % (lines_expected, len(pages)))

    if header_bad:
        report.add("C14", "ERROR", "源代码页眉缺少软件全称或格式不符: %d 页" % len(header_bad),
                   ", ".join("p%d=%s" % (p, t) for p, t in header_bad[:5]))
    else:
        report.add("C14", "INFO", "源代码页眉为 软件全称 + 版本号")

    if footer_bad:
        report.add("C34", "ERROR", "源代码页脚页码格式异常: %d 页" % len(footer_bad),
                   "应为 第 X 页 / 共 %d 页, 异常页: %s" % (
                       pages_expected, ", ".join("p%d" % p for p, _ in footer_bad[:8])))
    else:
        report.add("C34", "INFO", "源代码页脚页码格式正确")

    if mojibake:
        report.add("C15", "ERROR", "源代码 PDF 存在乱码或替换字符",
                   "页码: " + ", ".join(str(p) for p in mojibake[:10]))
    else:
        report.add("C15", "INFO", "源代码 PDF 无替换字符与典型乱码")

    check_probes(report, ctx)


def check_probes(report: Report, ctx: dict) -> None:
    probes = ctx["probes"]
    if not probes:
        report.add("C16", "WARN", "未找到可用于符号保留校验的探针",
                   "项目源码过少或未包含特殊符号")
        return
    flat = re.sub(r"\s+", "", "\n".join(ctx["source_pages"]))
    missing = [(label, token) for label, token in probes if re.sub(r"\s+", "", token) not in flat]
    if missing:
        level = "ERROR" if ctx.get("probes_strict") else "WARN"
        report.add("C16", level, "源代码特殊符号疑似丢失",
                   ", ".join("%s(%s)" % (label, token[:24]) for label, token in missing[:8]))
    else:
        report.add("C16", "INFO", "特殊符号与中文探针全部保留 (%d 项)" % len(probes))


def load_manifest_paths(src_pdf: Path | None, project: Path) -> set[str] | None:
    if src_pdf is None:
        return None
    candidates = []
    for path in src_pdf.parent.glob("*.json"):
        if "清单" in path.name or "manifest" in path.name.lower():
            candidates.append(path)
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        files = data.get("files") or []
        paths = {str(item.get("path", "")).replace("\\", "/") for item in files if item.get("path")}
        if paths:
            return paths
    return None


def build_probes(project: Path, selected: set[str] | None = None) -> tuple[list[tuple[str, str]], bool]:
    probes: list[tuple[str, str]] = []
    seen: set[str] = set()
    per_symbol: dict[str, int] = {}
    strict = selected is not None
    matched_any = False
    for path in project.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in CODE_EXTS:
            continue
        rel = path.relative_to(project)
        if any(p.lower() in SKIP_DIRS for p in rel.parts[:-1]):
            continue
        rel_posix = rel.as_posix()
        if selected is not None and rel_posix not in selected:
            continue
        matched_any = True
        try:
            text = read_plain(path)
        except OSError:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if not (8 <= len(stripped) <= 60):
                continue
            for label, pattern in SOURCE_PROBES:
                if per_symbol.get(label, 0) >= 3 or not re.search(pattern, stripped):
                    continue
                token = stripped
                if token in seen:
                    continue
                if not re.search(r"[\u4e00-\u9fff]", token) and label in ("查询管道", "星号", "装饰器"):
                    continue
                seen.add(token)
                per_symbol[label] = per_symbol.get(label, 0) + 1
                probes.append((label, token))
        if sum(per_symbol.values()) >= 15:
            break
    if selected is not None and not matched_any:
        return [], False
    return probes[:15], strict


def count_page_lines(pdf_path: Path) -> dict[int, int]:
    counts: dict[int, int] = {}
    try:
        import fitz  # type: ignore
        with fitz.open(str(pdf_path)) as doc:
            for idx, page in enumerate(doc, start=1):
                baselines = set()
                for block in page.get_text("dict")["blocks"]:
                    for line in block.get("lines", []):
                        spans = line.get("spans", [])
                        if not spans:
                            continue
                        y = round(spans[0]["origin"][1], 1)
                        text = "".join(s["text"] for s in spans).strip()
                        if not text:
                            continue
                        if y < 40.0 or y > 795.0:  # header and footer bands
                            continue
                        baselines.add(y)
                counts[idx] = len(baselines)
    except Exception:  # noqa: BLE001
        pass
    return counts


def check_manual(report: Report, ctx: dict, min_pages: int, max_pages: int, sparse: int) -> None:
    manual = ctx["manual"]
    if manual is None:
        return
    text = ctx["manual_text"]
    if not text.strip():
        report.add("C17", "ERROR", "说明书无法提取文字", "", str(manual))
        return
    images = ctx["manual_images"]
    if manual.suffix.lower() == ".pdf" and ctx["manual_pages"]:
        total = len(ctx["manual_pages"])
        if not (min_pages <= total <= max_pages):
            report.add("C17", "WARN", "说明书页数为 %d, 建议 %d 到 %d" % (total, min_pages, max_pages),
                       "", str(manual))
        else:
            report.add("C17", "INFO", "说明书页数: %d" % total)
        sparse_pages = []
        for idx, page_text in enumerate(ctx["manual_pages"], start=1):
            body = [ln for ln in page_text.splitlines()
                    if ln.strip() and not re.search(r"^\s*-?\s*\d+\s*-?\s*$", ln)]
            page_images = ctx["manual_page_images"].get(idx, 0)
            if len(body) < sparse and page_images == 0:
                sparse_pages.append(idx)
        if sparse_pages:
            report.add("C18", "WARN", "说明书存在稀疏空白页: " + ", ".join(map(str, sparse_pages[:12])),
                       "正文少于 %d 行且无图片, 建议合并或补充操作步骤" % sparse)
        else:
            report.add("C18", "INFO", "说明书无稀疏空白页")
    else:
        report.add("C17", "INFO", "说明书为 docx, 无固定分页信息",
                   "请导出 PDF 后复核页数是否在 %d 到 %d 之间" % (min_pages, max_pages))
        blanks = len(re.findall(r"\n\s*\n\s*\n\s*\n\s*\n", text))
        if blanks > 3:
            report.add("C18", "WARN", "说明书存在连续空段落: %d 处" % blanks)

    if images < 8:
        report.add("C19", "WARN", "说明书图片数量偏少: %d" % images,
                   "建议每个核心功能至少一张截图")
    else:
        report.add("C19", "INFO", "说明书图片数量: %d" % images)


def check_screenshots(report: Report, ctx: dict) -> None:
    shots = ctx["shots"]
    if shots is None:
        return
    files = sorted(p for p in shots.rglob("*") if p.suffix.lower() in IMAGE_EXTS)
    if not files:
        report.add("C20", "ERROR", "截图目录为空", "", str(shots))
        return
    small = []
    names = []
    for path in files:
        w, h = image_size(path)
        names.append(path.stem)
        if w and h and (w < 1280 or h < 720):
            small.append("%s(%dx%d)" % (path.name, w, h))
    if small:
        report.add("C21", "WARN", "截图分辨率不足 1280x720: %d 张" % len(small),
                   ", ".join(small[:6]))
    else:
        report.add("C21", "INFO", "截图分辨率全部达标 (%d 张)" % len(files))

    corpus = " ".join(names) + "\n" + ctx["manual_text"]
    missing = [label for label, pattern in SCENE_GROUPS.items()
               if not re.search(pattern, corpus)]
    if missing:
        report.add("C22", "WARN", "截图或说明书未覆盖场景: " + ", ".join(missing),
                   "需覆盖启动页、主工作台、核心操作、参数配置、导出或报告")
    else:
        report.add("C22", "INFO", "截图场景覆盖完整")

    suspicious = [n for n in names if re.search(r"报错|error|bug|测试|debug|临时|todo", n, re.IGNORECASE)]
    if suspicious:
        report.add("C23", "WARN", "截图文件名疑似异常或测试画面: " + ", ".join(suspicious[:6]))
    report.add("C24", "WARN", "截图内容需人工目视确认",
               "重点检查 NaN、Infinity、undefined、报错弹窗与日期")


def scan_source_tree(report: Report, project: Path, max_hits: int = 25) -> int:
    total = 0
    hits = 0
    for path in project.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in CODE_EXTS:
            continue
        rel = path.relative_to(project)
        if any(p.lower() in SKIP_DIRS for p in rel.parts[:-1]):
            continue
        try:
            lines = read_plain(path).splitlines()
        except OSError:
            continue
        total += sum(1 for ln in lines if ln.strip())
        for no, line in enumerate(lines, start=1):
            if hits >= max_hits:
                break
            if not re.search(r"^\s*(#|//|/\*|\*|<!--)", line):
                continue
            problems = []
            if re.search(r"\*\*[^*\n]+\*\*", line):
                problems.append("Markdown 加粗符")
            if re.search(r"为什么需要|好处\s*[:：]|代价\s*[:：]|权衡\s*[:：]", line):
                problems.append("自我辩论式注释")
            if re.search(r"禁止硬编码|必须遵循以下规则|作为\s*AI", line):
                problems.append("AI 规则提示词")
            if re.search(r"(?:^|\s)(?:P|B|C|T)[1-9]\d?\s*[:：]", line):
                problems.append("内部任务编号")
            if re.search(r"ChatGPT|GPT-[0-9]|Claude|AI\s*生成", line, re.IGNORECASE):
                problems.append("AI 产品痕迹")
            if problems:
                hits += 1
                report.add("C25", "WARN", "源码注释残留: " + ", ".join(problems),
                           line.strip()[:80], "%s:%d" % (rel.as_posix(), no))
    if hits == 0:
        report.add("C25", "INFO", "源码注释未发现 AI 痕迹")
    if total < 3000:
        report.add("C26", "WARN", "有效非空代码行数 %d, 少于 3000 行" % total,
                   "60 页每页 50 行需要 3000 行, 需补充模块")
    else:
        report.add("C26", "INFO", "有效非空代码行数: %d" % total)
    return total


def check_bom_residue(report: Report, project: Path) -> None:
    bad = bom_paths(project)
    if bad:
        report.add("C27", "WARN", "源码或文本文件存在 UTF-8 BOM: %d 个" % len(bad),
                   ", ".join(bad[:6]) + ("" if len(bad) <= 6 else " ..."))
    else:
        report.add("C27", "INFO", "未发现 UTF-8 BOM 残留")


def check_debug_strings(report: Report, project: Path, extra: list[str]) -> None:
    hits = 0
    scanned = 0
    for path in project.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in CODE_EXTS:
            continue
        rel = path.relative_to(project)
        if any(p.lower() in SKIP_DIRS or p.startswith(".") for p in rel.parts[:-1]):
            continue
        scanned += 1
        try:
            lines = read_plain(path).splitlines()
        except OSError:
            continue
        for no, line in enumerate(lines, start=1):
            if hits >= 20:
                break
            problems = [label for label, pattern in DEBUG_PATTERNS if re.search(pattern, line)]
            problems += ["个人标识:" + s for s in extra if s and s in line]
            if problems:
                hits += 1
                report.add("C28", "WARN", "疑似调试后门或个人标识: " + ", ".join(problems),
                           line.strip()[:90], "%s:%d" % (rel.as_posix(), no))
    if hits == 0:
        report.add("C28", "INFO", "未发现测试口令、彩蛋或硬编码凭据 (%d 个文件)" % scanned)


def share_block(text: str) -> str:
    match = re.search(r"按份共有[^\n\r]{0,300}", text or "")
    return match.group(0) if match else ""


def share_numbers(text: str) -> list[float]:
    """Collect percentages from sentences about shares or ratios.

    PDF extraction often breaks a clause across lines, so sentences are
    rebuilt by collapsing whitespace first. A sentence only counts when it
    carries at least two percentages or states the ownership mode, which
    keeps the owner table rows from being counted twice.
    """
    numbers: list[float] = []
    flat = re.sub(r"\s+", " ", text or "")
    for sentence in re.split(r"[。\n]", flat):
        if not ("%" in sentence or "％" in sentence):
            continue
        if not re.search(r"按份共有|份额|比例|占比", sentence):
            continue
        if re.search(r"序号|身份证号|手写签名|签字日期|信息表", sentence):
            continue
        found = split_share_numbers(sentence.replace("％", "%"))
        if len(found) >= 2 or "按份共有" in sentence:
            numbers.extend(found)
    if numbers:
        return numbers
    for line in (text or "").splitlines():
        if "%" not in line and "％" not in line:
            continue
        if re.search(r"按份共有|份额|比例|占比", line):
            numbers.extend(split_share_numbers(line.replace("％", "%")))
    return numbers


def check_owners(report: Report, ctx: dict) -> None:
    owners = ctx["owners"]
    mode = ctx["dev_mode"]
    if not owners:
        report.add("C29", "ERROR", "未提取到著作权人",
                   "申请表中需有 著作权人 字段并填写姓名或单位全称")
        return
    report.add("C29", "INFO", "著作权人: " + "、".join(owners))
    if mode == "合作开发" and len(owners) < 2:
        report.add("C29", "ERROR", "开发方式为合作开发, 但只提取到 1 名著作权人")
    if mode == "独立开发" and len(owners) > 1:
        report.add("C29", "ERROR", "开发方式为独立开发, 但提取到多名著作权人",
                   "个人申请只填 1 名自然人, 职务作品只填 1 个单位, 严禁混写")

    manual = ctx["manual_text"] or ""
    head = manual[:6000]
    positions = []
    missing = []
    for name in owners:
        pos = head.find(name)
        if pos < 0:
            missing.append(name)
        else:
            positions.append((pos, name))
    if missing:
        report.add("C29", "ERROR", "说明书封面未见著作权人: " + "、".join(missing),
                   "封面著作权人必须与申请表一致, 多人用顿号分隔")
    elif positions:
        ordered = [name for _, name in sorted(positions)]
        if ordered != owners:
            report.add("C29", "ERROR", "说明书著作权人顺序与申请表不一致",
                       "申请表: %s, 说明书: %s" % ("、".join(owners), "、".join(ordered)))
        else:
            report.add("C29", "INFO", "说明书著作权人顺序与申请表一致")

    all_owners = ctx["agreement_text"] or ""
    if all_owners and ctx["dev_mode"] == "合作开发":
        agreement_order = sorted(
            [(all_owners.find(name), name) for name in owners if all_owners.find(name) >= 0],
            key=lambda x: x[0])
        ordered = [name for _, name in agreement_order]
        if len(ordered) != len(owners):
            report.add("C29", "WARN", "合作开发协议未覆盖全部著作权人",
                       "缺少: " + "、".join(n for n in owners if n not in ordered))


def check_shares_and_agreement(report: Report, ctx: dict) -> None:
    owners = ctx["owners"]
    mode = ctx["dev_mode"]
    sharing = ctx["sharing"]
    required = mode == "合作开发" or len(owners) > 1

    app_block = share_block(ctx["app_text"])
    agreement_block = share_block(ctx["agreement_text"])
    if sharing == "按份共有":
        numbers = (share_numbers(ctx["app_text"])
                   or share_numbers(ctx["agreement_text"])
                   or extract_shares(app_block)
                   or extract_shares(agreement_block))
        if not numbers:
            report.add("C30", "ERROR", "按份共有未找到出资或权利比例",
                       "需按著作权人顺序写明各自百分比")
        else:
            total = round(sum(numbers), 2)
            if abs(total - 100.0) > 0.01:
                report.add("C30", "ERROR", "按份共有比例合计为 %s%%, 应为 100%%" % total,
                           "比例: " + ", ".join("%s%%" % n for n in numbers))
            else:
                report.add("C30", "INFO", "按份共有比例合计 100%")
    elif sharing == "共同共有":
        report.add("C30", "INFO", "权利归属为共同共有, 无需比例校验")
    elif required:
        report.add("C30", "WARN", "合作开发但未写明共同共有或按份共有",
                   "申请表与协议需明确权利归属方式")

    if not required:
        report.add("C31", "INFO", "独立开发, 无需合作开发协议")
        return

    docx_path = ctx["agreement_docx"]
    pdf_path = ctx["agreement_pdf"]
    if docx_path is None or pdf_path is None:
        missing = []
        if docx_path is None:
            missing.append("docx")
        if pdf_path is None:
            missing.append("pdf")
        report.add("C31", "ERROR", "缺少合作开发协议: " + ", ".join(missing),
                   "合作开发必须提供 合作开发协议-软件全称V1.0 的 docx 与 pdf")
        return
    report.add("C31", "INFO", "合作开发协议齐备",
               "%s / %s" % (docx_path.name, pdf_path.name))

    text = ctx["agreement_text"]
    if not text.strip():
        report.add("C31", "ERROR", "合作开发协议无法提取文字", "", str(docx_path))
        return
    if ctx["expected_name"] and norm_name(ctx["expected_name"]) not in norm_name(text):
        report.add("C31", "ERROR", "合作开发协议缺少软件全称", "", str(docx_path))
    if not re.search(r"共同共有|按份共有", text):
        report.add("C31", "ERROR", "合作开发协议未写明权利归属方式", "", str(docx_path))
    if not re.search(r"签字|签名", text):
        report.add("C31", "ERROR", "合作开发协议缺少签字栏", "", str(docx_path))
    ids = re.findall(r"\d{17}[\dXx]|\d{15}", text)
    if len(ids) < len(owners):
        report.add("C31", "WARN", "合作开发协议身份证号数量不足",
                   "应有 %d 个, 实际 %d 个" % (len(owners), len(ids)))


def check_game_branch(report: Report, ctx: dict) -> None:
    if not ctx["is_game"]:
        report.add("C32", "INFO", "通用软件, 跳过游戏专项截图清单")
        return
    corpus = " ".join(ctx["shot_names"]) + "\n" + (ctx["manual_text"] or "")
    missing_required = []
    missing_optional = []
    for label, pattern in GAME_SHOT_GROUPS.items():
        if re.search(pattern, corpus):
            continue
        if label in GAME_REQUIRED:
            missing_required.append(label)
        else:
            missing_optional.append(label)
    if missing_required:
        report.add("C32", "ERROR", "游戏专项截图缺少必选项: " + "、".join(missing_required),
                   "必选: 健康游戏忠告、非空角色或卡牌、通关闭环")
    if missing_optional:
        report.add("C32", "WARN", "游戏专项截图缺少建议项: " + "、".join(missing_optional))
    if not missing_required and not missing_optional:
        report.add("C32", "INFO", "游戏专项截图清单齐备")
    if re.search(r"暂无在任|暂无角色|空卡槽|敬请期待", corpus):
        report.add("C32", "ERROR", "截图或说明文字出现空面板字样",
                   "角色、卡牌、将领展示必须为非空状态")
    if ctx["shot_count"] < 12:
        report.add("C32", "WARN", "游戏截图数量偏少: %d" % ctx["shot_count"],
                   "全流程与全场景建议不少于 12 张")


def check_feature_txt(report: Report, ctx: dict) -> None:
    path = ctx["feature"]
    if path is None:
        report.add("C33", "WARN", "未找到 申请表-主要功能及技术特点.txt",
                   "建议单独输出纯文本, 便于直接粘贴官网表单")
        return
    text = read_plain(path)
    count = cjk_count(text)
    if not (ctx["min_desc"] <= count <= ctx["max_desc"]):
        report.add("C33", "ERROR", "功能描述文本汉字数为 %d, 应在 %d 到 %d" % (
            count, ctx["min_desc"], ctx["max_desc"]), "", str(path))
    else:
        report.add("C33", "INFO", "功能描述文本汉字数: %d" % count)
    tail = re.search(r"(汉字数|字数|共计|共\s*\d+\s*字)\s*[:：]?\s*\d*", text[-120:])
    if tail:
        report.add("C33", "ERROR", "功能描述文本末尾存在字数统计尾巴: " + tail.group(0),
                   "字数统计写入验收报告, 不要留在正文", str(path))
    if re.search(r"^\s*#|\*\*", text):
        report.add("C33", "WARN", "功能描述文本含 Markdown 标记", "", str(path))
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if cjk_count(p) >= 30]
    if len(paragraphs) < 5:
        report.add("C33", "WARN", "功能描述自然段不足 5 段: %d" % len(paragraphs), "", str(path))


# --------------------------------------------------------------------------
# entry
# --------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Preflight check for CPCC software copyright materials.")
    p.add_argument("--project", required=True, help="project root or material directory")
    p.add_argument("--name", default=None, help="expected software full name")
    p.add_argument("--version", default=None, help="expected version, e.g. V1.0")
    p.add_argument("--application", default=None, help="application form path")
    p.add_argument("--manual", default=None, help="manual path")
    p.add_argument("--source-pdf", default=None, help="source code pdf path")
    p.add_argument("--screenshots", default=None, help="screenshot directory")
    p.add_argument("--type", default="auto", choices=["auto", "general", "game"],
                   help="software type, auto detects from materials")
    p.add_argument("--personal-strings", default="",
                   help="extra personal handles to scan, comma separated")
    p.add_argument("--pages", type=int, default=60, help="expected source pdf pages")
    p.add_argument("--lines-per-page", type=int, default=50, help="expected lines per page")
    p.add_argument("--min-desc-chars", type=int, default=500)
    p.add_argument("--max-desc-chars", type=int, default=1300)
    p.add_argument("--manual-min-pages", type=int, default=10)
    p.add_argument("--manual-max-pages", type=int, default=25)
    p.add_argument("--sparse-lines", type=int, default=8)
    p.add_argument("--json", default=None, help="write json report here")
    p.add_argument("--strict", action="store_true", help="treat warnings as failures")
    p.add_argument("--scan-source", action="store_true", help="only scan source tree")
    p.add_argument("--quiet", action="store_true", help="only print errors and warnings")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project = Path(args.project).expanduser()
    if not project.is_dir():
        print("[ERROR] project is not a directory: %s" % project, file=sys.stderr)
        return 1

    report = Report()

    if args.scan_source:
        scan_source_tree(report, project)
        emit(report, args)
        return exit_code(report, args)

    app, manual, src_pdf, shots = find_artifacts(project)
    extras = find_extras(project)
    app = Path(args.application) if args.application else app
    manual = Path(args.manual) if args.manual else manual
    src_pdf = Path(args.source_pdf) if args.source_pdf else src_pdf
    shots = Path(args.screenshots) if args.screenshots else shots

    check_artifacts(report, app, manual, src_pdf, shots)

    app_text = read_any(app) if app else ""
    manual_text = read_any(manual) if manual else ""
    agreement_source = extras["agreement_docx"] or extras["agreement_pdf"]
    agreement_text = read_any(agreement_source) if agreement_source else ""
    manual_pages = read_pdf_pages(manual) if manual and manual.suffix.lower() == ".pdf" else []
    source_pages = read_pdf_pages(src_pdf) if src_pdf else []

    if not args.name:
        args.name = majority(collect_names(app_text)) or majority(collect_names(manual_text))
    if not args.version:
        derived = majority(collect_versions(app_text)) or majority(
            [norm_version(m) for m in re.findall(r"\bV\d+(?:\.\d+){1,3}\b", manual_text[:20000])])
        args.version = ("V" + derived) if derived else None

    manual_images = 0
    manual_page_images: dict[int, int] = {}
    if manual and manual.suffix.lower() == ".docx":
        try:
            import docx  # type: ignore
            manual_images = len(docx.Document(str(manual)).inline_shapes)
        except Exception:  # noqa: BLE001
            manual_images = 0
    elif manual and manual.suffix.lower() == ".pdf":
        try:
            import fitz  # type: ignore
            with fitz.open(str(manual)) as doc:
                for idx, page in enumerate(doc, start=1):
                    n = len(page.get_images(full=True))
                    manual_page_images[idx] = n
                    manual_images += n
        except Exception:  # noqa: BLE001
            pass

    shot_names: list[str] = []
    if shots:
        shot_names = [p.stem for p in shots.rglob("*") if p.suffix.lower() in IMAGE_EXTS]

    owners = extract_owners(app_text)
    dev_mode = extract_dev_mode(app_text)
    sharing = extract_sharing(app_text) or extract_sharing(agreement_text)
    is_game = is_game_software(app_text + "\n" + manual_text[:6000], args.type)
    personal = [s.strip() for s in args.personal_strings.split(",") if s.strip()]

    manifest_paths = load_manifest_paths(src_pdf, project)
    probes, probes_strict = build_probes(project, manifest_paths)

    ctx = {
        "application": app,
        "manual": manual,
        "source_pdf": src_pdf,
        "shots": shots,
        "app_text": app_text,
        "manual_text": manual_text,
        "feature": extras["feature"],
        "agreement_docx": extras["agreement_docx"],
        "agreement_pdf": extras["agreement_pdf"],
        "agreement_text": agreement_text,
        "owners": owners,
        "dev_mode": dev_mode,
        "sharing": sharing,
        "is_game": is_game,
        "shot_names": shot_names,
        "manual_pages": manual_pages,
        "manual_page_images": manual_page_images,
        "manual_images": manual_images,
        "source_pages": source_pages,
        "page_line_counts": count_page_lines(src_pdf) if src_pdf else {},
        "shot_count": len(shot_names),
        "expected_name": norm_name(args.name) if args.name else None,
        "expected_version": args.version,
        "min_desc": args.min_desc_chars,
        "max_desc": args.max_desc_chars,
        "probes": probes,
        "probes_strict": probes_strict,
    }

    check_consistency(report, ctx)
    check_description(report, ctx, args.min_desc_chars, args.max_desc_chars)
    check_dates(report, ctx)
    check_owners(report, ctx)
    check_shares_and_agreement(report, ctx)
    check_feature_txt(report, ctx)

    scan_text(report, "申请表", app_text, str(app or ""))
    scan_text(report, "说明书", manual_text, str(manual or ""))
    if source_pages:
        scan_text(report, "源代码 PDF", "\n".join(source_pages), str(src_pdf or ""))

    check_source_pdf(report, ctx, args.pages, args.lines_per_page)
    check_manual(report, ctx, args.manual_min_pages, args.manual_max_pages, args.sparse_lines)
    check_screenshots(report, ctx)
    check_game_branch(report, ctx)
    check_bom_residue(report, project)
    check_debug_strings(report, project, personal)
    scan_source_tree(report, project)

    emit(report, args)
    return exit_code(report, args)


def emit(report: Report, args: argparse.Namespace) -> None:
    for finding in report.findings:
        if args.quiet and finding.level == "INFO":
            continue
        print(finding)
    err = len(report.errors())
    warn = len(report.warns())
    info = len(report.findings) - err - warn
    print("")
    print("SUMMARY: %d ERROR, %d WARN, %d INFO" % (err, warn, info))
    if args.json:
        payload = {
            "project": str(args.project),
            "counts": {"error": err, "warn": warn, "info": info},
            "findings": [asdict(f) for f in report.findings],
        }
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("JSON report: %s" % args.json)


def exit_code(report: Report, args: argparse.Namespace) -> int:
    if report.errors():
        return 1
    if args.strict and report.warns():
        return 1
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
