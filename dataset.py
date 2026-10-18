"""Verify and unpack the team dataset without fetching anything from the network."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def unpack(archive, destination, expected_sha):
    archive, destination = Path(archive), Path(destination).resolve()
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected_sha:
        raise RuntimeError('数据集压缩包SHA256不匹配，已停止解压。')
    with zipfile.ZipFile(archive) as z:
        if sum(x.file_size for x in z.infolist()) > 200 * 1024 * 1024:
            raise RuntimeError('数据集解压大小超过限制。')
        for x in z.infolist():
            target = (destination.parent / x.filename).resolve()
            if not x.filename.startswith(destination.name + '/') or not target.is_relative_to(destination):
                raise RuntimeError('数据集包含越界路径，已停止解压。')
            if (x.external_attr >> 16) & 0o170000 == 0o120000:
                raise RuntimeError('数据集包含符号链接，已停止解压。')
        z.extractall(destination.parent)


def prepare_bundled_dataset():
    destination = ROOT / 'knowledge-base/v7'
    if (destination / 'P1-产品参数库').is_dir():
        return destination
    archive = ROOT / 'knowledge-base/v7.zip'
    manifest = ROOT / 'knowledge-base/dataset-manifest.json'
    if not archive.is_file() or not manifest.is_file():
        raise RuntimeError('仓库数据集缺失，请完整下载仓库或配置自己的 LOCAL_KB_PATH。')
    metadata = json.loads(manifest.read_text(encoding='utf-8'))
    unpack(archive, destination, metadata['sha256'])
    return destination
