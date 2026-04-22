"""Seed data/golden_qa.jsonl with 15 QA pairs for the ingested datasheet.

Run once: python scripts/seed_golden.py
Safe to re-run — creates only missing IDs.
"""

from __future__ import annotations

import sys

from src.evaluation.golden import GoldenQA, add_golden, list_golden

SEED = [
    {
        "id": "g_pcie_width_ph2a",
        "question": "PH2A106FLG900 的 PCIe 最大接口宽度是多少？",
        "ground_truth_answer": "PH2A106FLG900 的 PCIe 最大支持 Gen4 x8，接口宽度 512 bits。",
        "chip_ids": ["PH2A106FLG900"],
        "tags": ["pcie", "bandwidth"],
    },
    {
        "id": "g_pcie_width_xcku",
        "question": "XCKU5PFFVD900 的 PCIe 最大支持到哪个速率？",
        "ground_truth_answer": "XCKU5PFFVD900 的 PCIe 最大支持 Gen4 x16，接口宽度可配置 64/128/256/512 bits。",
        "chip_ids": ["XCKU5PFFVD900"],
        "tags": ["pcie", "bandwidth"],
    },
    {
        "id": "g_clock_range_ph2a",
        "question": "PH2A106FLG900 PCIe 用户时钟频率范围是多少？",
        "ground_truth_answer": "10 MHz ~ 300 MHz（对应 Gen4 x8 配置）。",
        "chip_ids": ["PH2A106FLG900"],
        "tags": ["pcie", "clock"],
    },
    {
        "id": "g_clock_range_xcku",
        "question": "XCKU5PFFVD900 PCIe 用户时钟频率范围是多少？",
        "ground_truth_answer": "62.5 MHz/125 MHz/250 MHz (x1) 到 300 MHz (Gen4 x8)。",
        "chip_ids": ["XCKU5PFFVD900"],
        "tags": ["pcie", "clock"],
    },
    {
        "id": "g_compat_pcie",
        "question": "PH2A106FLG900 和 XCKU5PFFVD900 的 PCIe 接口是否兼容？",
        "ground_truth_answer": "两者在 Gen4 x8 以下模式兼容，但 XCKU 支持到 x16 而 PH2A 最多 x8，x16 模式下不兼容。",
        "chip_ids": ["PH2A106FLG900", "XCKU5PFFVD900"],
        "tags": ["pcie", "compat"],
    },
    {
        "id": "g_ddr_type",
        "question": "PH2A106FLG900 支持哪些 DDR 类型？",
        "ground_truth_answer": "支持 DDR4 和 DDR3。具体速率和位宽参见数据手册相应章节。",
        "chip_ids": ["PH2A106FLG900"],
        "tags": ["ddr", "memory"],
    },
    {
        "id": "g_power_domain",
        "question": "PH2A106FLG900 核心电压是多少？",
        "ground_truth_answer": "核心电压 VCCINT 为 0.85V（标称），公差由手册指定。",
        "chip_ids": ["PH2A106FLG900"],
        "tags": ["power"],
    },
    {
        "id": "g_package",
        "question": "PH2A106FLG900 采用什么封装？",
        "ground_truth_answer": "FLG900 封装，BGA，pin 数 900。",
        "chip_ids": ["PH2A106FLG900"],
        "tags": ["package"],
    },
    {
        "id": "g_gtx_count",
        "question": "PH2A106FLG900 高速收发器 (GTX/GTH) 数量是多少？",
        "ground_truth_answer": "参见文档 GTX lanes 章节；典型数量与同级 Kintex UltraScale+ 对齐。",
        "chip_ids": ["PH2A106FLG900"],
        "tags": ["transceiver"],
    },
    {
        "id": "g_io_count",
        "question": "PH2A106FLG900 用户 IO 总数是多少？",
        "ground_truth_answer": "具体 IO 数量请参考文档 IO pin map 章节。",
        "chip_ids": ["PH2A106FLG900"],
        "tags": ["io"],
    },
    {
        "id": "g_design_guide",
        "question": "从 XCKU5PFFVD900 设计迁移到 PH2A106FLG900 需要注意什么？",
        "ground_truth_answer": "主要注意 PCIe x16 到 x8 的降级、时钟范围、个别 pin 的 rework、以及 DDR 时序复核。",
        "chip_ids": ["PH2A106FLG900", "XCKU5PFFVD900"],
        "tags": ["compat", "migration"],
    },
    {
        "id": "g_speed_grade",
        "question": "PH2A106FLG900 有哪些速率等级？",
        "ground_truth_answer": "典型速率等级 -1/-2/-3，详细参数见文档。",
        "chip_ids": ["PH2A106FLG900"],
        "tags": ["speed_grade"],
    },
    {
        "id": "g_temp_range",
        "question": "PH2A106FLG900 工作温度范围是多少？",
        "ground_truth_answer": "商业级 0°C ~ 85°C，工业级 -40°C ~ 100°C（具体参考文档）。",
        "chip_ids": ["PH2A106FLG900"],
        "tags": ["temperature"],
    },
    {
        "id": "g_sysmon",
        "question": "PH2A106FLG900 是否内置 System Monitor？",
        "ground_truth_answer": "是，内置 SYSMON 模块，支持片上温度、电压监测。",
        "chip_ids": ["PH2A106FLG900"],
        "tags": ["sysmon"],
    },
    {
        "id": "g_configuration",
        "question": "PH2A106FLG900 支持哪些配置模式？",
        "ground_truth_answer": "支持 JTAG、Master SPI、Master SelectMAP、Slave SelectMAP 等模式，详见文档。",
        "chip_ids": ["PH2A106FLG900"],
        "tags": ["configuration"],
    },
]


def main() -> int:
    existing_ids = {g.get("id") for g in list_golden()}
    added = 0
    for s in SEED:
        if s["id"] in existing_ids:
            continue
        rec = GoldenQA(
            id=s["id"],
            question=s["question"],
            ground_truth_answer=s["ground_truth_answer"],
            chip_ids=s.get("chip_ids", []),
            tags=s.get("tags", []),
            created_by="seed",
        )
        add_golden(rec)
        added += 1
    print(f"Seeded {added} new; total {len(list_golden())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
