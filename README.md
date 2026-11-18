# Cn_Software_Copyright

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)
![CPCC](https://img.shields.io/badge/CPCC-2026-red.svg)
![Checks](https://img.shields.io/badge/Preflight-34%20checks-brightgreen.svg)

跨 Agent 通用的中国版权保护中心 (CPCC) 计算机软件著作权登记自动化 Skill 工具包。面向 Claude Code、Cursor、Codex、Windsurf、ZCode 等支持 Agent Skills 标准的工具, 也支持完全脱离代理、直接以命令行方式使用。

它的目标不是替你编造材料, 而是把真实自研仓库高效整理为符合 CPCC 2026 年审查口径的四件套: 申请表功能文本、软件说明书、60 页源代码 PDF、合作开发协议, 并用 34 项自动化体检在提交前拦截常见补正点。

## 核心特性

- 先勘察后编号提问, 全流程零占位符。代理在生成任何文档前必须先只读扫描代码库, 再一次性提出 6 组编号问题, 信息未确认就不落笔, 避免 `[待填写]`、`TODO`、`TBD` 混入申报材料。
- 独立开发与合作开发双分流。独立申请强制单一著作权人, 严禁姓名与单位混写; 合作申请要求按申请表排名顺序录入全部著作权人、身份证号、开发分工与权利归属方式, 按份共有比例合计必须等于 100%。
- 通用软件与游戏软件双分支。游戏类自动启用专项截图门禁, 强制覆盖《健康游戏忠告》、带完整名称的主界面、非空角色或卡牌展示、全部可进入场景、可体验系统与通关闭环。
- 源代码 PDF 严格 60 页 × 50 行。读取源码优先 `utf-8-sig` 并显式剥离 BOM, 防止首行出现 `D` 或 `ï»¿` 前缀; 非 BMP 字符 (Emoji) 自动转义; 前 30 页取后端、核心逻辑与配置算法, 后 30 页取前端、交互与渲染模块; 页眉居中、页脚右对齐。
- 说明书自动化。读取 JSON 或 Markdown 章节配置, 生成带标准封面、软件全称与版本号页眉、页码页脚、等比缩放居中截图与图注的 docx; 检测到 Microsoft Word 或 LibreOffice 时自动导出 PDF。
- 合作开发协议自动生成。输出 docx 与 pdf, 载明软件信息、全部著作权人姓名与身份证号、开发分工、共有方式与比例、共同代表人、全体手写签字栏。
- 34 项自动化体检 C01-C34。覆盖四重一致性、功能描述字数与五段结构、占位符与 AI 痕迹、源码 PDF 页数行数与乱码、说明书稀疏页、截图分辨率与场景、BOM 残留、调试后门、著作权人顺序、按份比例、协议完整性、游戏专项清单与页眉页脚格式。
- 线下签章双保险指南。生成《后续线下签章与官网提交流程指南》, 明确实名认证、协议手写签名、A4 签章页、手机拍摄签章页照片上传至「其他相关证明文件」以及清理身份证临时文件五步。

## 目录结构

```text
Cn_Software_Copyright/
├── SKILL.md                     Skill 主指令: 阶段 0 至阶段 5 工作流与合规门禁
├── README.md                    本文件
├── LICENSE                      MIT License
├── requirements.txt             Python 依赖清单
├── .gitignore                   忽略缓存、虚拟环境与软著产物
└── scripts/
    ├── export_source_pdf.py     60 页 × 50 行源代码 PDF 导出
    ├── build_manual.py          结构化配置生成说明书 docx / pdf
    ├── build_agreement.py       合作开发协议 docx / pdf 生成
    └── preflight_check.py       C01-C34 自动化体检
```

## 工作流总览

| 阶段 | 动作 | 关键产物 |
| --- | --- | --- |
| 0 | 只读勘察技术栈、模块、入口、版本常量、有效行数 | 勘察摘要 |
| 1 | 编号提问, 确认主体形态、软件类型与登记信息 | 已确认信息表 |
| 2 | 独立分支清理 AI 痕迹、调试后门, 统一版本号 | 干净源码 + 重构导航 |
| 3 | 导出 60 页源代码 PDF | `05_源代码_V1.0_60页.pdf` |
| 4 | 生成说明书并采集真实截图 | `03/04_软件说明书_V1.0` |
| 5 | 生成功能文本、合作协议, 跑体检与流程指南 | 全套交付物 |

## 环境要求

- Python 3.9 或更高版本。
- 操作系统: Windows 10+, macOS, Linux。
- 必需依赖: `reportlab`、`python-docx`、`PyMuPDF`、`Pillow`。
- 可选依赖: `openpyxl` 用于读取 xlsx 申请表; `pywin32` 用于 Word COM 导出说明书 PDF。
- 可选软件: Microsoft Word 或 LibreOffice, 用于把说明书 docx 转为 pdf。

字体说明: Windows 默认使用 Consolas 与微软雅黑。macOS 与 Linux 如缺少内置候选字体, 请通过 `--font-mono` 与 `--font-cjk` 指定本机等宽与中文字体路径, 否则源码 PDF 会因找不到字体而退出。

## 快速安装

```bash
git clone https://github.com/<your-name>/Cn_Software_Copyright.git
cd Cn_Software_Copyright

python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## 挂载到多个 Agent

Skill 采用标准 `SKILL.md` + `scripts/` 结构, 既可被支持 Agent Skills 的工具自动发现, 也可手动挂载。核心原则是让各家全局 `skills` 目录指向本仓库同一份实体, 避免多份副本分叉。

### Windows PowerShell

```powershell
$src = "E:\path\to\Cn_Software_Copyright"
$targets = @(
    "$env:USERPROFILE\.agents\skills",
    "$env:USERPROFILE\.zcode\skills",
    "$env:USERPROFILE\.claude\skills",
    "$env:USERPROFILE\.cursor\skills",
    "$env:USERPROFILE\.codex\skills"
)
foreach ($dir in $targets) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    cmd /c mklink /J "$dir\Cn_Software_Copyright" "$src"
}
```

### macOS / Linux

```bash
SRC="$(pwd)"
for dir in "$HOME/.agents/skills" "$HOME/.zcode/skills" \
           "$HOME/.claude/skills" "$HOME/.cursor/skills" "$HOME/.codex/skills"; do
    mkdir -p "$dir"
    ln -sfn "$SRC" "$dir/Cn_Software_Copyright"
done
```

只想给某一个代理使用, 保留对应目录即可。使用 Windsurf 或其他工具时, 把同样的链接建到它约定的 skills 目录。

## 命令行独立使用

以下示例用 `<SKILL_DIR>` 表示本仓库根目录, `<PROJECT_DIR>` 表示被整理的业务项目根目录。所有脚本都支持 `--help` 查看完整参数。

### 1. 导出 60 页源代码 PDF

```bash
python "<SKILL_DIR>/scripts/export_source_pdf.py" \
  --root "<PROJECT_DIR>" \
  --name "智能排课管理系统" \
  --version V1.0 \
  --out "<PROJECT_DIR>/软著材料/05_源代码_V1.0_60页.pdf" \
  --manifest "<PROJECT_DIR>/软著材料/06_源代码清单.json"
```

常用开关:

- `--dry-run`: 只打印选材结果, 不生成 PDF。
- `--keep-blank`: 保留源码空行, 默认删除以保证每页 50 行都是有效代码。
- `--max-lines-per-file 600`: 限制单文件贡献行数, 防止巨型文件垄断页数。
- `--font-mono` / `--font-cjk`: 指定字体。
- `--fail-on-nonbmp`: 发现 Emoji 时直接失败, 默认转义为 `\U0001F600`。

### 2. 生成软件说明书

准备 `manual.json`:

```json
{
  "name": "智能排课管理系统",
  "version": "V1.0",
  "owner": "张三、李四",
  "date": "2026-11-18",
  "sections": [
    {
      "title": "1 软件概述",
      "paragraphs": ["本软件面向高校教务处的学期排课业务。"],
      "images": [
        {"path": "07_截图/01_启动页.png", "caption": "图 1 启动页"}
      ]
    }
  ]
}
```

也支持 Markdown: `- 软件全称: ...` 写封面字段, `## 章节` 分节, 空行分段, `![图注](路径)` 插图。

```bash
python "<SKILL_DIR>/scripts/build_manual.py" \
  --config "<PROJECT_DIR>/软著材料/manual.json" \
  --out-dir "<PROJECT_DIR>/软著材料"
```

输出 `03_软件说明书_V1.0.docx`。检测到 Word COM 或 LibreOffice 时自动输出 `04_软件说明书_V1.0.pdf`, 可用 `--no-pdf` 关闭, 或用 `--pdf-engine word|libreoffice` 指定后端。

### 3. 生成合作开发协议

```bash
python "<SKILL_DIR>/scripts/build_agreement.py" \
  --name "智能排课管理系统" \
  --version V1.0 \
  --date 2026-11-18 \
  --sharing "按份共有" \
  --owner "张三|110101199001011234|负责后端核心算法与数据库设计|60" \
  --owner "李四|310101199202022345|负责前端界面与交互实现|40" \
  --out-dir "<PROJECT_DIR>/软著材料"
```

`--owner` 格式为 `姓名|身份证号|开发分工|份额`, 可重复。脚本会校验身份证格式、至少两人、按份共有比例合计 100%、第一著作权人存在。上例中的姓名与身份证号均为演示数据, 请替换为真实信息。

### 4. 运行体检

```bash
python "<SKILL_DIR>/scripts/preflight_check.py" \
  --project "<PROJECT_DIR>" \
  --name "智能排课管理系统" \
  --version V1.0 \
  --type auto \
  --json "<PROJECT_DIR>/软著材料/10_体检报告.json" \
  --strict
```

`--type auto` 自动判断通用或游戏软件; 也可显式传 `general` 或 `game`。退出码 0 表示无错误, 1 表示存在 ERROR (加 `--strict` 时 WARN 也计为失败)。

## 体检检查项

| 分组 | 编号 | 覆盖内容 |
| --- | --- | --- |
| 交付物与一致性 | C01-C05 | 四类交付物齐备、软件全称、版本号、截图元信息、日期不得晚于开发完成日期 |
| 功能描述 | C06-C11 | 500-1300 汉字、五段结构、占位符、AI 痕迹、广告法风险词与套话、版本修饰词 |
| 源代码 PDF | C12-C16, C34 | 页数、每页 50 行、逐页页眉、乱码字符、特殊符号探针、页脚页码格式 |
| 软件说明书 | C17-C19 | 10-25 页、稀疏空白页、插图数量 |
| 界面截图 | C20-C24 | 数量、分辨率、场景覆盖、异常文件名、人工目视确认 |
| 源码卫生 | C25-C28 | AI 注释残留、有效非空行数、BOM 残留、个人调试字符串与后门 |
| 主体与协议 | C29-C31 | 著作权人数量与顺序、按份共有合计 100%、合作开发协议存在性与内容 |
| 分支与文本 | C32-C33 | 游戏专项截图清单、功能描述文本无字数统计尾巴 |

## 生成物结构

```text
软著材料/
  01_申请信息表.md
  02_申请表-主要功能及技术特点.txt
  03_软件说明书_V1.0.docx
  04_软件说明书_V1.0.pdf
  05_源代码_V1.0_60页.pdf
  06_源代码清单.json
  07_截图/
  08_合作开发协议-XXX系统V1.0.docx
  08_合作开发协议-XXX系统V1.0.pdf
  09_核心模块重构导航.md
  10_体检报告.json
  11_后续线下签章与官网提交流程指南.md
```

## 常见问题

- 源代码 PDF 中文显示为方框: 未正确嵌入中文字体, 用 `--font-cjk` 指定本机中文字体。
- 首行出现奇怪前缀字符: 源文件带 BOM, 本工具已用 `utf-8-sig` 剥离; 若使用其他工具导出, 请自行检查。
- 不足 3000 行: 有效非空代码不够 60 页, 需补充业务模块, 或接受页数不足的风险并书面说明。
- 说明书没有自动生成 PDF: 本机既无 Word 也无 LibreOffice, 安装其一, 或保留 docx 后手动导出。
- 体检报错 C29: 申请表、说明书封面、合作协议三处的著作权人数量或顺序不一致, 按申请表顺序统一。

## 隐私与安全

- 仓库不包含任何真实个人信息。文档中的张三、李四与身份证号均为虚构示例。
- 生成的 `软著材料/` 含身份证号与真实截图, 已在 `.gitignore` 中排除, 请勿提交。
- 建议每次申报结束后清理本地含身份证号的临时文件与导出中间件。

## 贡献

欢迎提交 Issue 与 Pull Request。提交前请确认:

1. 不包含真实个人身份信息与业务项目源码。
2. Python 代码通过 `python -m py_compile scripts/*.py`。
3. 新增体检规则时同步更新 `SKILL.md` 与 README 的检查项表格。

## License

本项目采用 [MIT License](LICENSE)。

## 合规声明

本工具仅用于辅助整理真实自研软件的登记材料与格式合规检查，使用者须严格遵守《计算机软件保护条例》及中国版权保护中心相关规定，确保核心代码与申报材料的原创性与真实性。
