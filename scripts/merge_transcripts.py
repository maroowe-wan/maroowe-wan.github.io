#!/usr/bin/env python3
"""
자막 파일들을 합쳐서 transcript.txt를 만드는 스크립트
"""
import os
import json
import glob
from pathlib import Path

def merge_transcripts(lecture_dir):
    """
    각 강의 폴더에서 sub_*.txt 파일들을 읽어 transcript.txt로 합친다.
    sources.json의 영상 순서를 유지한다.
    """
    # sources.json 읽기
    sources_json_path = os.path.join(lecture_dir, 'sources.json')
    if not os.path.exists(sources_json_path):
        print(f"sources.json 없음: {sources_json_path}")
        return False

    with open(sources_json_path, 'r', encoding='utf-8') as f:
        sources_data = json.load(f)

    selected_videos = sources_data.get('selected', [])
    if not selected_videos:
        print(f"선택된 영상 없음: {lecture_dir}")
        return False

    # transcript 내용 구성
    transcript_lines = []
    success_count = 0
    fail_count = 0

    for video_info in selected_videos:
        video_id = video_info['video_id']
        title = video_info['title']
        url = video_info['url']

        # 자막 파일 찾기
        sub_file = os.path.join(lecture_dir, f'sub_{video_id}.txt')

        if not os.path.exists(sub_file):
            print(f"  [실패] {video_id}: {title} - 자막 파일 없음")
            fail_count += 1
            continue

        # 자막 파일 읽기
        try:
            with open(sub_file, 'r', encoding='utf-8') as f:
                sub_content = f.read()

            # 헤더와 함께 추가
            transcript_lines.append(f"## 영상 {success_count + 1}: {title} ({url})\n")

            # "Kind: captions" 라인 이후의 내용만 추출
            lines = sub_content.split('\n')
            # 첫 2줄 제거 (Kind, Language)
            content_lines = []
            skip_lines = 0
            for line in lines:
                if skip_lines < 2:
                    if line.startswith('Kind:') or line.startswith('Language:'):
                        skip_lines += 1
                    continue
                content_lines.append(line)

            cleaned_content = '\n'.join(content_lines).strip()
            transcript_lines.append(cleaned_content)
            transcript_lines.append("")

            print(f"  [성공] {video_id}: {title}")
            success_count += 1
        except Exception as e:
            print(f"  [실패] {video_id}: {title} - {str(e)}")
            fail_count += 1

    if success_count == 0:
        print(f"추출된 자막 없음: {lecture_dir}")
        return False

    # transcript.txt 저장
    output_path = os.path.join(lecture_dir, 'transcript.txt')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(transcript_lines))

    print(f"  결과: {success_count} 성공, {fail_count} 실패")
    print(f"  저장: {output_path}\n")
    return True

# 강의 폴더들 처리
base_path = r'D:\02.project\업무자동화\edu-pipeline\courses\kafka-intermediate\lectures'
lecture_dirs = sorted(glob.glob(os.path.join(base_path, '*')))

print("=== Kafka Intermediate 강의 자막 병합 ===\n")

for lecture_dir in lecture_dirs:
    if os.path.isdir(lecture_dir):
        lecture_name = os.path.basename(lecture_dir)
        print(f"강의: {lecture_name}")
        merge_transcripts(lecture_dir)
