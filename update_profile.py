#!/usr/bin/env python3
"""Generate the auto-synced project section of the GitHub profile README."""
from __future__ import annotations

import json
import os
import re
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

USER = os.getenv("GITHUB_PROFILE_USER", "pgf20160610")
README = Path(__file__).with_name("README.md")
START = "<!-- AUTO-PROJECTS:START -->"
END = "<!-- AUTO-PROJECTS:END -->"

# A repository has one primary research direction. Technical stacks are shown as tags.
CATEGORY_RULES = [
    ("3D 感知与 BEV", ["pointpillars", "centerpoint", "bev", "pointcloud", "point-cloud", "lidar", "3d detection", "kitti", "nuscenes", "voxel"]),
    ("OCR 与文档智能", ["ocr", "paddleocr", "ppocr", "crnn", "ctc", "text recognition", "document", "license plate", "lpr"]),
    ("语音与音频 AI", ["asr", "whisper", "speech", "audio", "tasnet", "mossformer", "separator", "source separation"]),
    ("多模态 / VLM / VLA", ["vlm", "vla", "multimodal", "llava", "qwen-vl", "openvla", "smolvla", "lerobot", "vision-language"]),
    ("机器人 / ROS2 / 标定", ["ros2", "ros", "robot", "robotics", "slam", "calibration", "sensorx", "autoware", "camera-lidar", "lidar-camera"]),
    ("2D 视觉 / 检测 / 姿态", ["yolo", "pose", "keypoint", "detection", "detector", "tracking", "segment", "sam", "lane", "depth", "face"]),
    ("边缘 AI 部署", ["onnx", "mnn", "rknn", "tensorrt", "qnn", "deployment", "deploy", "inference", "edge-ai", "ncnn", "openvino"]),
]

TAG_RULES = {
    "C++": ["c++", "cpp", "cxx"],
    "Python": ["python"],
    "YOLO": ["yolo"],
    "Pose": ["pose", "keypoint"],
    "OCR": ["ocr", "crnn", "paddleocr", "ppocr"],
    "ASR": ["asr", "whisper", "speech"],
    "3D": ["pointpillars", "centerpoint", "3d", "pointcloud", "lidar"],
    "BEV": ["bev"],
    "ROS2": ["ros2"],
    "ONNX": ["onnx"],
    "MNN": ["mnn"],
    "RKNN": ["rknn"],
    "TensorRT": ["tensorrt"],
    "VLM": ["vlm", "vision-language", "multimodal"],
    "VLA": ["vla", "openvla", "smolvla", "lerobot"],
}

EXCLUDED = {USER.lower(), "pgf-ai-portfolio"}


def api_get(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USER}-profile-sync",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def fetch_repos():
    repos = []
    page = 1
    while True:
        url = f"https://api.github.com/users/{USER}/repos?per_page=100&page={page}&sort=updated"
        batch = api_get(url)
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return [
        r for r in repos
        if not r.get("fork")
        and not r.get("archived")
        and r.get("name", "").lower() not in EXCLUDED
    ]


def repo_text(repo):
    values = [
        repo.get("name", ""),
        repo.get("description") or "",
        repo.get("language") or "",
        " ".join(repo.get("topics") or []),
    ]
    return " ".join(values).lower()


def primary_category(repo):
    text = repo_text(repo)
    scored = []
    for index, (category, keywords) in enumerate(CATEGORY_RULES):
        score = sum(2 if kw in (repo.get("topics") or []) else 1 for kw in keywords if kw in text)
        if score:
            scored.append((score, -index, category))
    return max(scored)[2] if scored else "其他 AI / 工程项目"


def tags(repo):
    text = repo_text(repo)
    result = []
    language = repo.get("language")
    if language:
        result.append(language)
    for label, keywords in TAG_RULES.items():
        if label not in result and any(k in text for k in keywords):
            result.append(label)
    for topic in repo.get("topics") or []:
        if topic not in result:
            result.append(topic)
    return result[:8]


def esc(text):
    return str(text or "").replace("\n", " ").strip()


def build_section(repos):
    groups = defaultdict(list)
    for repo in repos:
        groups[primary_category(repo)].append(repo)

    order = [c for c, _ in CATEGORY_RULES] + ["其他 AI / 工程项目"]
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    lines = [
        START,
        f"> 自动同步自 GitHub Public API · 共 **{len(repos)}** 个公开非 Fork 项目 · 更新于 `{now}`",
        "",
        "项目会根据仓库名称、Description、Topics 和主要语言自动归入一个研究方向；技术栈可多标签展示。",
        "",
    ]

    for category in order:
        items = groups.get(category, [])
        if not items:
            continue
        items.sort(key=lambda r: r.get("pushed_at") or r.get("updated_at") or "", reverse=True)
        lines += [f"## {category}", ""]
        for repo in items:
            name = esc(repo.get("name"))
            url = repo.get("html_url", f"https://github.com/{USER}/{name}")
            desc = esc(repo.get("description")) or "暂无项目说明。"
            tag_text = " ".join(f"`{t}`" for t in tags(repo))
            pushed = (repo.get("pushed_at") or repo.get("updated_at") or "")[:10]
            stars = repo.get("stargazers_count", 0)
            lines += [
                f"### [{name}]({url})",
                f"{desc}",
                "",
                f"{tag_text} · ⭐ {stars} · 更新 `{pushed}`",
                "",
            ]

    lines.append(END)
    return "\n".join(lines)


def main():
    content = README.read_text(encoding="utf-8")
    repos = fetch_repos()
    section = build_section(repos)
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if pattern.search(content):
        content = pattern.sub(section, content)
    else:
        content += "\n\n" + section + "\n"
    README.write_text(content, encoding="utf-8")
    print(f"Updated {README} with {len(repos)} repositories")


if __name__ == "__main__":
    main()
