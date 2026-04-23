"""P0 golden 扩充脚本：向 data/golden_qa.jsonl 追加 40 条基于《PH2A106FLG900 &
XCKU5PFFVD900 兼容设计指南》的高质量单芯片 QA。

所有答案都来自已入库的 98 条 chunks，可被 RAG 真实召回 + grounding 校验通过。

分层：A 单参数数值 14 条 / B 对比 10 条 / C Y-N 特性 6 条 / D 设计规则 6 条 / E 应拒答 4 条 = 40 条。

运行： .venv/bin/python scripts/expand_golden_p0.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "data" / "golden_qa.jsonl"

CHIP = "PH2A106FLG900"
BASELINE_XCKU = "XCKU5PFFVD900"
SRC = "《PH2A106FLG900 & XCKU5PFFVD900 兼容设计指南》"
CREATED_BY = "claude-p0-expand-2026-04-23"

RECORDS: list[dict] = [
    # ---------- A. 单参数数值查询 (14) ----------
    {"qid": "p0_pcie_width", "tags": ["pcie", "single_param"],
     "q": f"{CHIP} 的 PCIe 接口宽度是多少 bit？",
     "a": "PH2A106FLG900 PCIe 控制器接口宽度为 512 bits。"},
    {"qid": "p0_pcie_max_mps", "tags": ["pcie", "single_param"],
     "q": f"{CHIP} PCIe 最大 MPS (Max Payload Size) 是多少字节？",
     "a": "PH2A106FLG900 PCIe 控制器最大 MPS 为 4096 Bytes。"},
    {"qid": "p0_pcie_vf_count", "tags": ["pcie", "single_param"],
     "q": f"{CHIP} PCIe 支持多少个 VF 通道？",
     "a": "PH2A106FLG900 PCIe 控制器支持 256 个 VF 通道。"},
    {"qid": "p0_dsp_count", "tags": ["dsp", "single_param"],
     "q": f"{CHIP} DSP 总数是多少？",
     "a": "PH2A106FLG900 的 DSP 总数为 1,800 个。"},
    {"qid": "p0_lut6_count", "tags": ["plb", "single_param"],
     "q": f"{CHIP} LUT6 数量是多少？",
     "a": "PH2A106FLG900 的 LUT6 数量为 246,720。"},
    {"qid": "p0_register_count", "tags": ["plb", "single_param"],
     "q": f"{CHIP} 寄存器 (Register) 数量是多少？",
     "a": "PH2A106FLG900 的寄存器数量为 493,440。"},
    {"qid": "p0_dram_capacity", "tags": ["plb", "single_param"],
     "q": f"{CHIP} 分布式 RAM (DRAM) 总容量是多少？",
     "a": "PH2A106FLG900 的 DRAM 容量为 5,370K。"},
    {"qid": "p0_eram_40k_blocks", "tags": ["eram", "single_param"],
     "q": f"{CHIP} 40Kb ERAM Block 数量是多少？",
     "a": "PH2A106FLG900 有 600 个 40Kb ERAM Block（或 1200 个 20Kb Block）。"},
    {"qid": "p0_eram144k_size", "tags": ["eram_144k", "single_param"],
     "q": f"{CHIP} ERAM_144K 的单块容量是多少？",
     "a": "PH2A106FLG900 ERAM_144K 单块容量为 144Kb，共 120 个 Block。"},
    {"qid": "p0_pll_input_upper", "tags": ["pll", "single_param"],
     "q": f"{CHIP} PLL Input Range 上限是多少 MHz？",
     "a": "PH2A106FLG900 PLL 输入频率范围上限为 1066 MHz（范围 10-1066 MHz）。"},
    {"qid": "p0_pll_vco_range", "tags": ["pll", "single_param"],
     "q": f"{CHIP} PLL VCO 频率范围是多少？",
     "a": "PH2A106FLG900 PLL VCO 范围为 800-2000 MHz。"},
    {"qid": "p0_hxt_peak_speed", "tags": ["hxt", "single_param"],
     "q": f"{CHIP} HXT 高速收发器的峰值线速率是多少 Gbps？",
     "a": "PH2A106FLG900 HXT 峰值线速率为 26.6 Gbps；其中 BANK82 的 4 条 lane 最高仅支持 12.5 Gbps。"},
    {"qid": "p0_ddr4_speed", "tags": ["ddr", "single_param"],
     "q": f"{CHIP} DDR4 最高支持速率是多少 Mbps？",
     "a": "PH2A106FLG900 DDR4 最高支持 2800 Mbps。"},
    {"qid": "p0_gclk_freq", "tags": ["clock", "single_param"],
     "q": f"{CHIP} GCLK 最高时钟频率是多少？",
     "a": "PH2A106FLG900 GCLK 最高时钟频率为 775 MHz。"},

    # ---------- B. 对比问题 (10) ----------
    {"qid": "p0_cmp_dsp", "tags": ["compare", "dsp"],
     "q": f"{CHIP} 与 {BASELINE_XCKU} 的 DSP 数量有什么差异？",
     "a": "PH2A106FLG900 有 1,800 个 DSP，XCKU5PFFVD900 有 1,824 个，差 24 个。"},
    {"qid": "p0_cmp_hxt_quad", "tags": ["compare", "hxt"],
     "q": f"{CHIP} 与 {BASELINE_XCKU} 的 HXT/GTY Quad 数量分别是多少？",
     "a": "PH2A106FLG900 HXT 有 5 个 Quad，XCKU5PFFVD900 GTY 有 4 个 Quad。"},
    {"qid": "p0_cmp_pcie_gen", "tags": ["compare", "pcie"],
     "q": f"{CHIP} 与 {BASELINE_XCKU} PCIe Gen 支持有什么差异？",
     "a": "PH2A106FLG900 PCIe 仅支持 Gen1/Gen2/Gen3（x1/x2/x4/x8）；XCKU5PFFVD900 支持到 Gen4（x1/x2/x4/x8/x16）。"},
    {"qid": "p0_cmp_bitstream", "tags": ["compare", "config"],
     "q": f"{CHIP} 与 {BASELINE_XCKU} 所需 bitstream FLASH 最小容量是多少？",
     "a": "PH2A106FLG900 需要 256Mb FLASH（bitstream ~188Mb）；XCKU5PFFVD900 需要 128Mb FLASH（bitstream ~123Mb）。"},
    {"qid": "p0_cmp_seu_maxfreq", "tags": ["compare", "seu"],
     "q": f"{CHIP} 与 {BASELINE_XCKU} 的 SEU 最大支持频率差多少？",
     "a": "PH2A106FLG900 SEU 最大频率为 3 MHz；XCKU5PFFVD900 为 100 MHz。差值约 97 MHz。"},
    {"qid": "p0_cmp_dna", "tags": ["compare", "config"],
     "q": f"{CHIP} 与 {BASELINE_XCKU} 的 Device ID DNA 位宽分别是多少？",
     "a": "PH2A106FLG900 DNA 为 64 bit；XCKU5PFFVD900 DNA 为 56 bit。"},
    {"qid": "p0_cmp_pkg_thickness", "tags": ["compare", "package"],
     "q": f"{CHIP} 与 {BASELINE_XCKU} 封装厚度分别是多少？",
     "a": "PH2A106FLG900（FLG900）厚度 3.206+0.196/-0.194 mm；XCKU5PFFVD900（FFVD900）厚度 3.22±0.2 mm。"},
    {"qid": "p0_cmp_thermal_ja0", "tags": ["compare", "thermal"],
     "q": f"{CHIP} 与 {BASELINE_XCKU} 的 θJa（0 LFM）热阻分别是多少？",
     "a": "PH2A106FLG900 θJa(0LFM) 为 6.43 ℃/W；XCKU5PFFVD900 为 9.00 ℃/W。PH2A 散热更好。"},
    {"qid": "p0_cmp_ddr4", "tags": ["compare", "ddr"],
     "q": f"{CHIP} 与 {BASELINE_XCKU} DDR4 最高速率分别是多少？",
     "a": "PH2A106FLG900 DDR4 最高 2800 Mbps；XCKU5PFFVD900 DDR4 最高 2666 Mbps。"},
    {"qid": "p0_cmp_eram_blocksize", "tags": ["compare", "eram"],
     "q": f"{CHIP} 与 {BASELINE_XCKU} ERAM Block Size 有什么差别？",
     "a": "PH2A106FLG900 ERAM Block Size 为 40Kb/20Kb；XCKU5PFFVD900 为 36Kb/18Kb。"},

    # ---------- C. Y/N 特性支持 (6) ----------
    {"qid": "p0_yn_2x50ge", "tags": ["mac100g", "y_n"],
     "q": f"{CHIP} 是否支持 2 x 50GE MAC 配置？",
     "a": "支持。PH2A106FLG900 的 100G MAC 支持 2 x 50GE 配置（XCKU5PFFVD900 不支持）。"},
    {"qid": "p0_yn_caui10", "tags": ["mac100g", "y_n"],
     "q": f"{CHIP} 是否支持 1 x 100GE CAUI-10？",
     "a": "不支持。PH2A106FLG900 的 100G MAC 不支持 CAUI-10；仅支持 CAUI-4。"},
    {"qid": "p0_yn_jesd204b", "tags": ["hxt", "y_n"],
     "q": f"{CHIP} HXT 是否支持 JESD204B 协议？",
     "a": "支持。PH2A106FLG900 HXT 支持 JESD204B。"},
    {"qid": "p0_yn_hdio_lvcmos12", "tags": ["io", "y_n"],
     "q": f"{CHIP} HD IO 是否支持 LVCMOS12 电平？",
     "a": "不支持。PH2A106FLG900 HD IO 不支持 LVCMOS12（HP IO 支持）。"},
    {"qid": "p0_yn_dsp_pattern", "tags": ["dsp", "y_n"],
     "q": f"{CHIP} DSP 是否支持 Pattern 检测？",
     "a": "不支持。PH2A106FLG900 DSP 不提供 Pattern 检测（XCKU5PFFVD900 支持）。"},
    {"qid": "p0_yn_io_hotplug", "tags": ["io", "y_n"],
     "q": f"{CHIP} 的 HP/HD IO 是否支持热插拔？",
     "a": "不支持。PH2A106FLG900 的 HP 和 HD IO 均不支持热插拔，BANK 必须严格遵循上下电顺序。"},

    # ---------- D. 设计规则 / 连接要求 (6) ----------
    {"qid": "p0_rule_power_seq", "tags": ["power", "design_rule"],
     "q": f"{CHIP} 推荐的上电顺序是什么？",
     "a": "PH2A106FLG900 推荐上电顺序为 V_CCINT → V_CCAUX → V_CCIO；下电顺序与上电相反。若 V_CCAUX 与 V_CCIO 电压相同，允许两者同时上下电。"},
    {"qid": "p0_rule_hp_vccio", "tags": ["power", "io", "design_rule"],
     "q": f"{CHIP} HP BANK 的 V_CCIO 是否支持 1.0 V？",
     "a": "不支持。PH2A106FLG900 HP BANK V_CCIO 范围为 1.14 V – 1.89 V，不支持 1.0 V 电平。"},
    {"qid": "p0_rule_hd_vccio", "tags": ["power", "io", "design_rule"],
     "q": f"{CHIP} HD BANK 的 V_CCIO 是否支持 1.2 V？",
     "a": "不支持。PH2A106FLG900 HD BANK V_CCIO 范围为 1.425 V – 3.4 V，不支持 1.2 V 电平。"},
    {"qid": "p0_rule_done_pullup", "tags": ["config", "design_rule"],
     "q": f"{CHIP} DONE 引脚 (AB12) 的外部电路连接要求是什么？",
     "a": "PH2A106FLG900 的 DONE 引脚应使用不超过 4.7 kΩ 的电阻上拉到 VCCIO_0，作为加载完成指示。"},
    {"qid": "p0_rule_programn_pullup", "tags": ["config", "design_rule"],
     "q": f"{CHIP} PROGRAMN 引脚 (AG11) 的外部电阻要求是什么？",
     "a": "PH2A106FLG900 的 PROGRAMN 引脚需通过不超过 4.7 kΩ 的外部电阻上拉到 VCCIO_0，作为配置复位。"},
    {"qid": "p0_rule_hxt_unused", "tags": ["hxt", "design_rule"],
     "q": f"{CHIP} 若不使用 HXT 模块，电源应如何处理？",
     "a": "PH2A106FLG900 不使用 HXT 时，需让 PHYVCCA / PHYVCCT 保持上电（进入 standby 状态仅产生静态功耗），不影响 AC/DC 指标；REFCLKP/N、RXP/N 接 GND，TXP/N 悬空。无需额外接参考电阻。"},

    # ---------- E. 应触发拒答 / 数据不在指南内 (4) ----------
    {"qid": "p0_abstain_typ_power", "tags": ["abstain", "power"],
     "q": f"{CHIP} 的典型工作功耗是多少瓦？",
     "a": f"暂无法给出可靠答案。{SRC} 仅给出电源电压与电源域连接要求，未提供典型功耗（W）数值；需参考官方 Datasheet 的 Power 章节或 Power Estimator 工具。"},
    {"qid": "p0_abstain_op_temp", "tags": ["abstain", "environment"],
     "q": f"{CHIP} 的工作温度范围是多少？",
     "a": f"暂无法给出可靠答案。{SRC} 未包含温度等级或工作温度范围信息；需查阅官方 Datasheet 的 Ordering Information 或 Recommended Operating Conditions。"},
    {"qid": "p0_abstain_price", "tags": ["abstain", "commercial"],
     "q": f"{CHIP} 单价是多少？",
     "a": "暂无法给出可靠答案。价格信息不在技术文档中，请联系芯片厂商或经销商获取正式报价。"},
    {"qid": "p0_abstain_crypto", "tags": ["abstain", "security"],
     "q": f"{CHIP} 支持哪种 bitstream 加密算法（AES/RSA/ECDSA）？",
     "a": f"暂无法给出可靠答案。{SRC} 为硬件兼容性设计指南，未披露 bitstream 加密算法细节（仅提到 DNA 与 Dual/Multi Boot 功能）；需查阅官方 Datasheet 的 Security 章节。"},
]


def build_entry(rec: dict, now: float) -> dict:
    return {
        "id": f"g_{rec['qid']}",
        "question": rec["q"],
        "ground_truth_answer": rec["a"],
        "ground_truth_contexts": [],
        "chip_ids": [CHIP] + ([BASELINE_XCKU] if "compare" in rec["tags"] else []),
        "tags": rec["tags"],
        "created_by": CREATED_BY,
        "created_at": now,
    }


def main() -> int:
    if not GOLDEN.exists():
        print(f"ERROR: {GOLDEN} missing", file=sys.stderr)
        return 2

    existing_ids = set()
    for line in GOLDEN.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            existing_ids.add(json.loads(line).get("id"))
        except json.JSONDecodeError:
            pass

    now = time.time()
    appended = 0
    skipped = 0
    with GOLDEN.open("a", encoding="utf-8") as f:
        for r in RECORDS:
            gid = f"g_{r['qid']}"
            if gid in existing_ids:
                skipped += 1
                continue
            entry = build_entry(r, now)
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            appended += 1

    print(f"Appended {appended} new golden records ({skipped} duplicates skipped)")
    total = sum(1 for _ in GOLDEN.open(encoding="utf-8"))
    print(f"Total records in {GOLDEN}: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
