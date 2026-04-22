"""Seed a small, real-world demo dataset so RAG queries return something.

Populates:
- PostgreSQL `chips` + `chip_parameters` (3 MCUs)
- Milvus `datasheet_chunks` (~15 chunks) with BGE-M3 dense+sparse vectors

Run from the repo root:
    .venv/bin/python scripts/seed_demo_data.py
"""
from __future__ import annotations

import os
import sys
from typing import Any

import httpx
import psycopg2
from pymilvus import Collection, connections

EMBED_URL = os.environ.get("EMBED_URL", "http://localhost:8001")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "bed58e34123f29d7e8ce6902fccfa059")
MILVUS_HOST = os.environ.get("MILVUS_HOST", "localhost")
MILVUS_PORT = os.environ.get("MILVUS_PORT", "19530")

# --- Chip catalog (id, part_number, manufacturer, etc.) ---
CHIPS: list[dict[str, Any]] = [
    {
        "id": 1,
        "part_number": "STM32F407VGT6",
        "manufacturer": "STMicroelectronics",
        "category": "MCU",
        "family": "STM32F4",
        "package": "LQFP100",
        "pin_count": 100,
        "status": "active",
        "description": "High-performance Arm Cortex-M4 MCU with FPU, 168 MHz, 1 MB Flash, 192 KB SRAM.",
    },
    {
        "id": 2,
        "part_number": "GD32F407VGT6",
        "manufacturer": "GigaDevice",
        "category": "MCU",
        "family": "GD32F4",
        "package": "LQFP100",
        "pin_count": 100,
        "status": "active",
        "description": "Pin-to-pin compatible alternative to STM32F407, Arm Cortex-M4, 168 MHz, 1 MB Flash.",
    },
    {
        "id": 3,
        "part_number": "STM32F103C8T6",
        "manufacturer": "STMicroelectronics",
        "category": "MCU",
        "family": "STM32F1",
        "package": "LQFP48",
        "pin_count": 48,
        "status": "active",
        "description": "Mainstream Arm Cortex-M3 MCU, 72 MHz, 64 KB Flash, 20 KB SRAM.",
    },
]

PARAMS: list[tuple[int, str, str, str]] = [
    (1, "max_frequency_mhz", "168", "MHz"),
    (1, "flash_size_kb", "1024", "KB"),
    (1, "sram_size_kb", "192", "KB"),
    (1, "vcc_min_v", "1.8", "V"),
    (1, "vcc_max_v", "3.6", "V"),
    (1, "temp_min_c", "-40", "C"),
    (1, "temp_max_c", "85", "C"),
    (2, "max_frequency_mhz", "168", "MHz"),
    (2, "flash_size_kb", "1024", "KB"),
    (2, "sram_size_kb", "192", "KB"),
    (3, "max_frequency_mhz", "72", "MHz"),
    (3, "flash_size_kb", "64", "KB"),
    (3, "sram_size_kb", "20", "KB"),
]

# --- Datasheet chunk content (chip_id, part_number, manufacturer, doc_type, page, section, content) ---
CHUNKS: list[dict[str, Any]] = [
    {
        "chunk_id": "stm32f407-01",
        "chip_id": 1,
        "part_number": "STM32F407VGT6",
        "manufacturer": "STMicroelectronics",
        "doc_type": "datasheet",
        "page": 1,
        "section": "Features Overview",
        "content": (
            "STM32F407VGT6 is a high-performance microcontroller based on the "
            "Arm Cortex-M4 32-bit RISC core with single-precision FPU and DSP "
            "instructions. It operates at a maximum CPU frequency of 168 MHz, "
            "providing 210 DMIPS / 1.25 DMIPS/MHz at 168 MHz. The device includes "
            "a memory protection unit (MPU) and embedded trace macrocell (ETM)."
        ),
    },
    {
        "chunk_id": "stm32f407-02",
        "chip_id": 1,
        "part_number": "STM32F407VGT6",
        "manufacturer": "STMicroelectronics",
        "doc_type": "datasheet",
        "page": 2,
        "section": "Memories",
        "content": (
            "STM32F407VGT6 integrates up to 1 MB of Flash memory and 192+4 KB of "
            "SRAM (including 64 KB of CCM data RAM). Flash memory accelerator "
            "(ART Accelerator) delivers zero-wait-state performance at 168 MHz."
        ),
    },
    {
        "chunk_id": "stm32f407-03",
        "chip_id": 1,
        "part_number": "STM32F407VGT6",
        "manufacturer": "STMicroelectronics",
        "doc_type": "datasheet",
        "page": 3,
        "section": "Power Supply",
        "content": (
            "Power supply range is 1.8 V to 3.6 V. Operating temperature range "
            "is -40 to +85 C (industrial). Low-power modes include Sleep, Stop, "
            "and Standby; Stop mode current is typically 350 uA, Standby is 4 uA."
        ),
    },
    {
        "chunk_id": "stm32f407-04",
        "chip_id": 1,
        "part_number": "STM32F407VGT6",
        "manufacturer": "STMicroelectronics",
        "doc_type": "datasheet",
        "page": 5,
        "section": "Peripherals",
        "content": (
            "Peripherals include 3x 12-bit ADCs (up to 24 channels), 2x 12-bit "
            "DACs, 17 timers (including two 32-bit and twelve 16-bit), 3x SPI, "
            "3x I2C, 4x USART + 2x UART, 2x CAN, 1x SDIO, 2x USB OTG (FS and HS), "
            "1x Ethernet MAC 10/100, and 1x camera interface (DCMI)."
        ),
    },
    {
        "chunk_id": "stm32f407-05",
        "chip_id": 1,
        "part_number": "STM32F407VGT6",
        "manufacturer": "STMicroelectronics",
        "doc_type": "datasheet",
        "page": 8,
        "section": "Clock System",
        "content": (
            "Clock sources: 4-to-26 MHz HSE crystal oscillator, 16 MHz HSI RC, "
            "32.768 kHz LSE crystal, 32 kHz LSI RC. Two embedded PLLs can generate "
            "the 168 MHz main system clock and additional clocks for USB OTG FS "
            "(48 MHz), the random number generator, and the SDIO interface."
        ),
    },
    {
        "chunk_id": "stm32f407-06",
        "chip_id": 1,
        "part_number": "STM32F407VGT6",
        "manufacturer": "STMicroelectronics",
        "doc_type": "datasheet",
        "page": 12,
        "section": "Package",
        "content": (
            "The STM32F407VGT6 is supplied in an LQFP100 14x14 mm package with "
            "100 pins, 82 of which are GPIOs. All I/Os are 5 V tolerant except "
            "for analog inputs."
        ),
    },
    {
        "chunk_id": "gd32f407-01",
        "chip_id": 2,
        "part_number": "GD32F407VGT6",
        "manufacturer": "GigaDevice",
        "doc_type": "datasheet",
        "page": 1,
        "section": "Overview",
        "content": (
            "GD32F407VGT6 is a 32-bit general-purpose microcontroller based on "
            "the Arm Cortex-M4 core, operating at up to 168 MHz with FPU. It is "
            "designed as a pin-to-pin and software-compatible alternative to "
            "STM32F407VGT6, offering 1 MB Flash and 192 KB SRAM."
        ),
    },
    {
        "chunk_id": "gd32f407-02",
        "chip_id": 2,
        "part_number": "GD32F407VGT6",
        "manufacturer": "GigaDevice",
        "doc_type": "datasheet",
        "page": 2,
        "section": "Compatibility",
        "content": (
            "GD32F407 is hardware-compatible with STM32F407 on the LQFP100 "
            "package and shares the same peripheral register map for most "
            "standard peripherals, allowing drop-in replacement in typical "
            "designs with minimal firmware changes."
        ),
    },
    {
        "chunk_id": "stm32f103-01",
        "chip_id": 3,
        "part_number": "STM32F103C8T6",
        "manufacturer": "STMicroelectronics",
        "doc_type": "datasheet",
        "page": 1,
        "section": "Overview",
        "content": (
            "STM32F103C8T6 is a mainstream microcontroller based on the Arm "
            "Cortex-M3 core running at up to 72 MHz. It features 64 KB Flash, "
            "20 KB SRAM, and is housed in an LQFP48 package. Typical applications "
            "include motor control, home appliances, and industrial sensors."
        ),
    },
    {
        "chunk_id": "stm32f103-02",
        "chip_id": 3,
        "part_number": "STM32F103C8T6",
        "manufacturer": "STMicroelectronics",
        "doc_type": "datasheet",
        "page": 3,
        "section": "Peripherals",
        "content": (
            "Peripherals include 2x 12-bit ADCs (up to 16 channels), 7 DMA "
            "channels, 3 timers, 2x SPI, 2x I2C, 3x USART, 1x USB FS 2.0, "
            "1x CAN 2.0B. Operating voltage 2.0 V to 3.6 V."
        ),
    },
    {
        "chunk_id": "stm32f407-vs-f103",
        "chip_id": 1,
        "part_number": "STM32F407VGT6",
        "manufacturer": "STMicroelectronics",
        "doc_type": "app_note",
        "page": 1,
        "section": "Comparison",
        "content": (
            "Compared to STM32F103 (Cortex-M3, 72 MHz, 64 KB Flash), the "
            "STM32F407 provides roughly 2.3x the clock speed, 16x the Flash, "
            "9.6x the SRAM, hardware single-precision FPU, and a more extensive "
            "peripheral set including Ethernet, USB HS, and two 12-bit DACs."
        ),
    },
]


def encode_texts(texts: list[str]) -> tuple[list[list[float]], list[dict[int, float]]]:
    resp = httpx.post(
        f"{EMBED_URL}/encode",
        json={"texts": texts, "return_sparse": True},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    dense: list[list[float]] = data["dense"]
    sparse_raw = data.get("sparse") or []
    sparse: list[dict[int, float]] = []
    for s in sparse_raw:
        sparse.append({int(k): float(v) for k, v in s.items()} if isinstance(s, dict) else {})
    return dense, sparse


def seed_postgres() -> None:
    conn = psycopg2.connect(
        host="localhost", port=5432, dbname="chipwise",
        user="chipwise", password=PG_PASSWORD,
    )
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM chips")
        if cur.fetchone()[0] > 0:
            print("[pg] chips already populated, skipping")
            return
        for c in CHIPS:
            cur.execute(
                """INSERT INTO chips
                (id, part_number, manufacturer, category, family, package, pin_count, status, description)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO NOTHING""",
                (c["id"], c["part_number"], c["manufacturer"], c["category"],
                 c["family"], c["package"], c["pin_count"], c["status"], c["description"]),
            )
        for cid, name, val, unit in PARAMS:
            cur.execute(
                """INSERT INTO chip_parameters
                (chip_id, parameter_name, parameter_category, typ_value, unit)
                VALUES (%s,%s,%s,%s,%s)""",
                (cid, name, "electrical", float(val), unit),
            )
        conn.commit()
        print(f"[pg] inserted {len(CHIPS)} chips and {len(PARAMS)} parameters")
    finally:
        conn.close()


def seed_milvus() -> None:
    connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
    col = Collection("datasheet_chunks")
    col.load()
    if col.num_entities > 0:
        print(f"[milvus] collection has {col.num_entities} entities already, skipping")
        return

    texts = [c["content"] for c in CHUNKS]
    print(f"[milvus] encoding {len(texts)} chunks via BGE-M3…")
    dense, sparse = encode_texts(texts)

    rows: list[dict[str, Any]] = []
    for c, d, s in zip(CHUNKS, dense, sparse):
        row: dict[str, Any] = {
            "chunk_id": c["chunk_id"],
            "dense_vector": d,
            "chip_id": c["chip_id"],
            "part_number": c["part_number"],
            "manufacturer": c["manufacturer"],
            "doc_type": c["doc_type"],
            "page": c["page"],
            "section": c["section"],
            "content": c["content"],
            "collection": "datasheet_chunks",
        }
        if s:
            row["sparse_vector"] = s
        rows.append(row)

    result = col.insert(rows)
    col.flush()
    print(f"[milvus] inserted {len(rows)} chunks, insert_count={result.insert_count}")
    print(f"[milvus] collection now has {col.num_entities} entities")


if __name__ == "__main__":
    try:
        seed_postgres()
        seed_milvus()
        print("Seed complete.")
    except Exception as exc:  # noqa: BLE001
        print(f"Seed failed: {exc}", file=sys.stderr)
        raise
