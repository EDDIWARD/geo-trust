from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
from pathlib import Path
from urllib.parse import quote


DATABASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = DATABASE_DIR.parent.parent
DEFAULT_DB_PATH = DATABASE_DIR / "android_backend.db"
DEFAULT_SOURCE_DIR = REPO_ROOT / "产品数据"
DEFAULT_STATIC_DIR = REPO_ROOT / "backend" / "server" / "static" / "product-media"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm"}
ALIAS_MAP = {
    "湛江小龙虾": "潜江小龙虾",
}
PROCESS_DESCRIPTIONS = {
    "恩施玉露": "记录茶园采摘、摊青与制茶核心工艺，确保批次工序可追溯。",
    "赤壁青砖茶": "记录原料筛选、渥堆发酵与压砖工艺，形成完整加工轨迹。",
    "神农架百花蜜": "记录蜂场采蜜、初滤澄清与灌装封存过程，体现山地蜜源品质。",
    "秭归脐橙": "记录果园管护、采摘分选与包装入库流程，体现产地鲜采品质。",
    "宜昌高山柚": "记录柚园管理、成熟采收与分级包装流程，保证高山柚来源可信。",
    "罗田板栗": "记录山地采收、筛选风干与分装流程，保证板栗批次信息清晰。",
    "武汉莲藕粉": "记录鲜藕清洗、制浆烘干与成品包装过程，确保工艺节点可回溯。",
    "潜江小龙虾": "记录生态养殖、净养分拣与冷链包装流程，体现鲜活水产流转信息。",
    "洪山菜薹": "记录基地采收、分拣保鲜与冷链发运流程，呈现蔬菜当日流转状态。",
    "梁子湖大闸蟹": "记录湖区捕捞、分拣暂养与冷链打包过程，保证水域来源可信。",
    "随州香菇": "记录菌棚培育、采摘烘干与质检包装过程，保证香菇产区信息完整。",
    "孝感米酒": "记录浸米发酵、糖化调配与成品灌装流程，体现传统米酒工艺。",
    "绍兴黄酒": "记录冬酿发酵、陈储调和与装瓶流程，保证黄酒生产批次可查。",
    "西湖龙井": "记录鲜叶采摘、杀青辉锅与包装封存过程，突出核心茶区工艺。",
    "阳澄湖大闸蟹": "记录湖区养殖、起捕分拣与冷链出货流程，确保核心湖区来源可信。",
}


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def canonical_name(name: str) -> str:
    return ALIAS_MAP.get(name.strip(), name.strip())


def slugify(name: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", name.strip(), flags=re.UNICODE)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned or "product"


def copy_media_file(src: Path, static_root: Path, product_key: str) -> str:
    target_dir = static_root / slugify(product_key)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / src.name
    shutil.copy2(src, target_path)
    relative_path = target_path.relative_to(static_root.parent)
    return "/static/" + "/".join(quote(part) for part in relative_path.parts)


def find_first(folder: Path, keywords: tuple[str, ...], extensions: set[str]) -> Path | None:
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        if not keywords or any(keyword in path.stem for keyword in keywords):
            return path
    return None


def find_all(folder: Path, keywords: tuple[str, ...], extensions: set[str]) -> list[Path]:
    matches: list[Path] = []
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        if any(keyword in path.stem for keyword in keywords):
            matches.append(path)
    return matches


def load_external_video(folder: Path) -> str | None:
    link_file = folder / "视频链接.txt"
    if not link_file.exists():
        return None
    for line in link_file.read_text(encoding="utf-8").splitlines():
        value = line.strip().rstrip("，。；;")
        if value.startswith("http://") or value.startswith("https://"):
            return value
    return None


def build_process_steps(product_key: str, process_image_url: str | None) -> list[tuple[int, str, str, str, str | None]]:
    titles = [
        "产区采集",
        "初步加工",
        "质量检验",
        "包装入库",
    ]
    description = PROCESS_DESCRIPTIONS.get(product_key, f"{product_key} 的核心产地与加工流程已归档，可用于消费端溯源展示。")
    return [
        (1, titles[0], f"{description} 已完成原料采集登记。", "产区环节", process_image_url),
        (2, titles[1], f"{description} 已完成初加工与生产留痕。", "加工环节", process_image_url),
        (3, titles[2], f"{description} 已完成抽检与资质核验。", "质检环节", process_image_url),
        (4, titles[3], f"{description} 已完成包装入库并生成追溯编码。", "包装环节", process_image_url),
    ]


def import_one_folder(connection: sqlite3.Connection, folder: Path, static_root: Path) -> dict[str, object]:
    product_key = canonical_name(folder.name)
    display_name = folder.name

    product_image_file = (
        find_first(folder, ("产品图片", "产品图", "产品展示", "产品"), IMAGE_EXTENSIONS)
        or find_first(folder, ("商品展示",), IMAGE_EXTENSIONS)
    )
    process_image_file = find_first(folder, ("生产过程", "生产现场"), IMAGE_EXTENSIONS)
    gallery_files = []
    for candidate in find_all(folder, ("商品展示", "基地环境", "基地", "生产现场", "产品展示"), IMAGE_EXTENSIONS):
        if product_image_file and candidate == product_image_file:
            continue
        if process_image_file and candidate == process_image_file and "生产现场" in candidate.stem:
            continue
        gallery_files.append(candidate)

    cert_files = find_all(folder, ("原产地证明", "产地证明", "卫生证书", "卫生证明", "质检报告"), IMAGE_EXTENSIONS)
    local_video_file = find_first(folder, tuple(), VIDEO_EXTENSIONS)
    external_video_url = load_external_video(folder)

    if product_image_file is None:
        raise RuntimeError(f"未找到产品主图: {folder}")

    product_image_url = copy_media_file(product_image_file, static_root, product_key)
    process_image_url = copy_media_file(process_image_file, static_root, product_key) if process_image_file else None
    gallery_payload = [
        ("商品展示" if "商品" in path.stem or "产品展示" in path.stem else "基地环境" if "基地" in path.stem else "生产现场",
         copy_media_file(path, static_root, product_key))
        for path in gallery_files[:3]
    ]
    cert_payload = [
        (path.stem, copy_media_file(path, static_root, product_key))
        for path in cert_files[:3]
    ]

    video_url = None
    source_type = None
    if local_video_file is not None:
        video_url = copy_media_file(local_video_file, static_root, product_key)
        source_type = "local"
    elif external_video_url:
        video_url = external_video_url
        source_type = "external"

    with connection:
        connection.execute("DELETE FROM product_media_profiles WHERE product_key = ?", (product_key,))
        connection.execute("DELETE FROM product_process_profiles WHERE product_key = ?", (product_key,))
        connection.execute("DELETE FROM product_video_profiles WHERE product_key = ?", (product_key,))

        connection.execute(
            """
            INSERT INTO product_media_profiles (product_key, display_name, media_type, title, file_url, sort_order)
            VALUES (?, ?, 'product_image', ?, ?, 1)
            """,
            (product_key, display_name, "产品主图", product_image_url),
        )

        sort_order = 1
        for title, file_url in cert_payload:
            connection.execute(
                """
                INSERT INTO product_media_profiles (product_key, display_name, media_type, title, file_url, sort_order)
                VALUES (?, ?, 'cert', ?, ?, ?)
                """,
                (product_key, display_name, title, file_url, sort_order),
            )
            sort_order += 1

        sort_order = 1
        for title, file_url in gallery_payload:
            connection.execute(
                """
                INSERT INTO product_media_profiles (product_key, display_name, media_type, title, file_url, sort_order)
                VALUES (?, ?, 'gallery', ?, ?, ?)
                """,
                (product_key, display_name, title, file_url, sort_order),
            )
            sort_order += 1

        if process_image_url:
            connection.execute(
                """
                INSERT INTO product_media_profiles (product_key, display_name, media_type, title, file_url, sort_order)
                VALUES (?, ?, 'video_cover', ?, ?, 1)
                """,
                (product_key, display_name, "视频封面", process_image_url),
            )

        for step_no, title, description, time_text, image_url in build_process_steps(product_key, process_image_url or product_image_url):
            connection.execute(
                """
                INSERT INTO product_process_profiles (product_key, step_no, title, description, image_url, time_text)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (product_key, step_no, title, description, image_url, time_text),
            )

        if video_url:
            connection.execute(
                """
                INSERT INTO product_video_profiles (product_key, title, video_url, cover_url, source_type, duration_seconds, sort_order)
                VALUES (?, ?, ?, ?, ?, 0, 1)
                """,
                (
                    product_key,
                    f"{product_key}产地溯源视频",
                    video_url,
                    process_image_url or product_image_url,
                    source_type or "local",
                ),
            )

    return {
        "product_key": product_key,
        "display_name": display_name,
        "gallery_count": len(gallery_payload),
        "cert_count": len(cert_payload),
        "has_video": bool(video_url),
    }


def import_media(db_path: Path, source_dir: Path, static_root: Path) -> list[dict[str, object]]:
    if not db_path.exists():
        raise RuntimeError(f"数据库不存在: {db_path}")
    if not source_dir.exists():
        raise RuntimeError(f"产品数据目录不存在: {source_dir}")

    static_root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    with connect(db_path) as connection:
        for folder in sorted(path for path in source_dir.iterdir() if path.is_dir()):
            results.append(import_one_folder(connection, folder, static_root))
        connection.commit()
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Import product media into SQLite and static directory.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path.")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE_DIR), help="Source folder containing product assets.")
    parser.add_argument("--static-root", default=str(DEFAULT_STATIC_DIR), help="Static output directory.")
    args = parser.parse_args()

    results = import_media(Path(args.db), Path(args.source), Path(args.static_root))
    print(f"Imported {len(results)} product media folders.")
    for item in results:
        print(
            f"{item['display_name']}: certs={item['cert_count']}, "
            f"gallery={item['gallery_count']}, video={'yes' if item['has_video'] else 'no'}"
        )


if __name__ == "__main__":
    main()
