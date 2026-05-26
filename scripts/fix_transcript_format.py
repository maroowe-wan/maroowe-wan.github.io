#!/usr/bin/env python3
"""transcript.txt 형식을 기존 강좌와 맞추기"""
import re
from pathlib import Path

def fix_format(lecture_path):
    """## 영상: → ## 영상 N: 형식으로 변경"""
    transcript_file = lecture_path / 'transcript.txt'
    if not transcript_file.exists():
        return False
    
    with open(transcript_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # ## 영상: 패턴을 찾아 순번을 붙임
    lines = content.split('\n')
    new_lines = []
    counter = 1
    
    for line in lines:
        if line.startswith('## 영상:'):
            # "## 영상: Title (url)" → "## 영상 1: Title (url)"
            # "영상:" 다음 공백을 제거하지 않음
            rest = line[len('## 영상:'):]
            new_line = f"## 영상 {counter}:{rest}"
            new_lines.append(new_line)
            counter += 1
        else:
            new_lines.append(line)
    
    with open(transcript_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))
    
    return True

base_path = Path('D:/02.project/업무자동화/edu-pipeline/courses/kubernetes-advanced/lectures')

for lecture_dir in sorted(base_path.iterdir()):
    if lecture_dir.is_dir():
        fix_format(lecture_dir)
        print("Fixed: " + lecture_dir.name)
