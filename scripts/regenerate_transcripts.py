#!/usr/bin/env python3
"""각 강의의 자막들을 sources.json 순서대로 합쳐서 transcript.txt 생성"""
import json
import os
import sys
from pathlib import Path

def clean_subtitle_text(text):
    """자막 헤더 제거 및 기본 정리"""
    lines = text.split('\n')
    # "Kind: captions", "Language: ..." 헤더 제거
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('Kind:') or stripped.startswith('Language:'):
            continue
        if stripped:
            cleaned.append(line)
    return '\n'.join(cleaned).strip()

def combine_lecture_transcripts(lecture_path):
    """강의 폴더 내의 자막들을 sources.json 순서대로 합치기"""
    sources_file = lecture_path / 'sources.json'
    if not sources_file.exists():
        print("[ERROR] " + str(sources_file) + " not found")
        return False
    
    with open(sources_file, encoding='utf-8') as f:
        sources = json.load(f)
    
    transcript_parts = []
    counter = 1
    
    for video in sources.get('selected', []):
        video_id = video['video_id']
        title = video['title']
        url = video['url']
        
        sub_file = lecture_path / f'sub_{video_id}.txt'
        if not sub_file.exists():
            print("[WARN] " + str(sub_file) + " not found")
            continue
        
        # 자막 읽기
        with open(sub_file, encoding='utf-8') as f:
            sub_text = f.read()
        
        # 헤더 제거
        cleaned = clean_subtitle_text(sub_text)
        
        # 강의 부분 추가 - 기존 형식: "## 영상 N: Title (url)"
        transcript_parts.append(f"## 영상 {counter}: {title} ({url})\n\n{cleaned}\n")
        counter += 1
    
    if not transcript_parts:
        print("[ERROR] No subtitles found for " + str(lecture_path))
        return False
    
    # transcript.txt 저장
    transcript_file = lecture_path / 'transcript.txt'
    with open(transcript_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(transcript_parts))
    
    print("[OK] " + str(transcript_file) + " saved")
    return True

def main():
    base_path = Path('D:/02.project/업무자동화/edu-pipeline/courses/kubernetes-advanced/lectures')
    
    for lecture_dir in sorted(base_path.iterdir()):
        if lecture_dir.is_dir():
            print("\nProcessing: " + lecture_dir.name)
            combine_lecture_transcripts(lecture_dir)

if __name__ == '__main__':
    main()
