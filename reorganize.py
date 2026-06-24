# -*- coding: utf-8 -*-
import os, re

d = r'C:\Users\chenyuhao\Desktop\大学\课程\物联网\考试'
target = None
for f in os.listdir(d):
    if f.endswith('.md') and ('复习' in f or 'ϰ' in f):
        target = os.path.join(d, f)
        break
with open(target, 'r', encoding='utf-8') as f:
    text = f.read()

chapters = ['第1章', '第2章', '第3章', '第4章', '第5章', '第6章', '第7章', '第8章', '第9章', '第10章']
ch_titles = ['绪论', '参考模型与技术体系', '感知', '标识', '定位与授时', '网络', '计算', '大数据与人工智能', '安全与隐私保护', '应用']

# ----- Parse sections -----
lines = text.split('\n')

# Find section boundaries
short_start = None
detail_start = None
qa_start = None
for i, ln in enumerate(lines):
    s = ln.strip()
    if '核心知识点速查矩阵' in s and '详解' not in s:
        short_start = i
    elif '核心知识点详解' in s:
        detail_start = i
    elif s == '## 例题与题库':
        qa_start = i

# Helper: get content between two markers
def get_section(from_line, to_line):
    return '\n'.join(lines[from_line:to_line])

# Parse short sections per chapter
short_sections = {}
current_ch = None
start_i = short_start
for i in range(short_start, detail_start if detail_start else len(lines)):
    s = lines[i].strip()
    for ch in chapters:
        if s.startswith('### ' + ch) and '【' not in s:
            if current_ch:
                short_sections[current_ch] = (start_i, i)
            current_ch = ch
            start_i = i
            break
if current_ch:
    short_sections[current_ch] = (start_i, detail_start if detail_start else len(lines))

# Parse detail sections per chapter
detail_sections = {}
current_ch = None
start_i = detail_start
for i in range(detail_start if detail_start else 0, qa_start if qa_start else len(lines)):
    s = lines[i].strip()
    for ch in chapters:
        if s.startswith('### ' + ch) and '【详解】' in s:
            if current_ch:
                detail_sections[current_ch] = (start_i, i)
            current_ch = ch
            start_i = i
            break
    # Also catch supplement sections like "### 第5章 定位与授时【定位技术补充】"
    for ch in chapters:
        if s.startswith('### ' + ch) and '【' in s and '【详解】' not in s:
            # These are supplements - include them in their chapter
            pass
if current_ch:
    detail_sections[current_ch] = (start_i, qa_start if qa_start else len(lines))

# Parse questions per chapter
qa_sections = {ch: [] for ch in chapters}
current_section = None
for i in range(qa_start if qa_start else 0, len(lines)):
    s = lines[i].strip()
    if s.startswith('### ') and not s.startswith('### ' + chapters[0]):
        for ch in chapters:
            if s.startswith('### ' + ch):
                current_section = s
                break
    # Check for chapter tags on question lines
    matched_ch = None
    for ch in chapters:
        tag = f'[章节 {ch[-1]}]'
        if tag in s:
            matched_ch = ch
            break
    if matched_ch:
        qa_sections[matched_ch].append(i)

# ----- Get detail supplements (extra sections like 【补充细节】) -----
# These are already included in detail_sections ranges

# ----- Build new file -----
new_parts = []
new_parts.append('# 物联网开卷考试速查宝典（按章节整理）\n')

# Add TOC
new_parts.append('\n## 总目录\n')
for i, ch in enumerate(chapters):
    anchor = ch + ' ' + ch_titles[i]
    new_parts.append(f'- [{anchor}](#{anchor.replace(" ", "-")})\n')

# Get the header content (before short_start)
header = '\n'.join(lines[1:short_start]).strip()
# Only keep the TOC from header

# For each chapter, gather: short + detail + questions
for idx, ch in enumerate(chapters):
    new_parts.append(f'\n---\n# {ch} {ch_titles[idx]}\n')

    # 1. Short knowledge matrix
    if ch in short_sections:
        s, e = short_sections[ch]
        content = get_section(s, e).strip()
        # Remove the leading ### chapter heading since we already have h1
        content_lines = content.split('\n')
        # Just add the content as-is under the h1
        new_parts.append('## 知识点速查\n')
        new_parts.append(content + '\n')

    # 2. Detailed knowledge
    if ch in detail_sections:
        s, e = detail_sections[ch]
        content = get_section(s, e).strip()
        if content:
            new_parts.append('## 知识点详解\n')
            new_parts.append(content + '\n')

    # 3. Questions for this chapter
    ch_num = ch[-1]
    if ch == '第10章':
        ch_num = '10'

    related = []
    in_section = False
    section_start = qa_start if qa_start else 0
    for i in range(section_start, len(lines)):
        s = lines[i].strip()
        # Check for section headers like ### 单选题
        if s.startswith('### ') and ('选' in s or '答' in s or '案例' in s or '思考' in s or '论述' in s or '对照' in s or '必考' in s or '快速' in s or 'RFID' in s or 'MQTT' in s):
            in_section = True
            continue
        if in_section:
            tag = f'[章节 {ch_num}]'
            if tag in s:
                # Collect this question (all lines until next question or section)
                q_lines = []
                j = i
                while j < len(lines):
                    next_line = lines[j].strip()
                    # break at next question or section
                    if j > i:
                        next_tag = None
                        for c in range(1, 11):
                            t = f'[章节 {c}]'
                            if t in next_line and next_line.startswith('['):
                                break
                        else:
                            if next_line.startswith('['):
                                # Not a chapter-tagged question, might be continuation
                                pass
                            if next_line.startswith('### ') or next_line.startswith('#### '):
                                break
                    q_lines.append(lines[j])
                    j += 1
                    if j >= len(lines):
                        break
                    # Check if we hit a new tagged question
                    nl = lines[j].strip()
                    for c in range(1, 11):
                        if f'[章节 {c}]' in nl and nl.startswith('['):
                            break
                    else:
                        if nl.startswith('[') and ']' in nl and '答案' not in nl:
                            break
                if q_lines:
                    related.extend(q_lines)
                    i = j - 1

    if related:
        new_parts.append('## 相关题目\n')
        new_parts.append(''.join(related) + '\n')

# Write output
output = '\n'.join(new_parts)
# Clean up excessive blank lines
output = re.sub(r'\n{4,}', '\n\n\n', output)

outpath = os.path.join(d, '复习_按章节整理.md')
with open(outpath, 'w', encoding='utf-8') as f:
    f.write(output)

print(f"Done! Written to {repr(outpath)}")
print(f"Total lines: {len(output.splitlines())}")
