# ChipWise Enterprise — Agent 协作工作日志

> 本文档是 **Claude Code** 与 **GitHub Copilot** 两个 Agent 之间的"接力棒"。
> 任何一方在本项目做工作前后，都应在此文件**追加**一条记录（不要改写历史）。
> 目的：当一方没有 token 额度时，另一方能够立即接手且不丢失上下文。

**维护规则**：
1. 每次开始工作：写「开始」条目（谁 / 时间 / 目标 / 当前理解的上下文）。
2. 每次结束工作：写「结束」条目（改了什么文件 / 测试结果 / 遗留问题 / 下一步建议）。
3. 只追加、不删除；如果发现前一条有误，写一条"更正"条目说明。
4. 所有相对时间（"昨天"）都转成绝对日期（`YYYY-MM-DD`）。
5. 涉及的文件路径一律用项目根相对路径（如 `src/agent/orchestrator.py`）。
6. 分 3 种条目类型：`### [Claude]`、`### [Copilot]`、`### [User]`（用户口头决策也记录）。

---

## 📌 项目当前状态快照（2026-04-23 由 Claude 维护）

### 版本与阶段
- **DEV SPEC 版本**：v5.7（2026-04-22，`docs/ENTERPRISE_DEV_SPEC.md`）
- **已完成阶段**：Phase 1–12 + Phase 12.1（共 126 个任务项）
- **最近一次提交**：`11c17af docs(spec): align v5.7 with Phase 12.1/12.2 — agent budget bump + UI redesign rows`
- **最近一次功能提交**：`690146f feat: Phase 12 + 12.1 — RAG evaluation closed loop + grounding hallucination guard`

### 部署环境
- 机器：极摩客 NucBoxEVO-X2（AMD Ryzen AI 395，128 GB RAM，WSL2）
- 工作目录：`/home/mech-mindai/ChipWise-Enterprise`
- Python venv：`/home/mech-mindai/ChipWise-Enterprise/.venv`
- 当前分支：`main`（工作树干净）

### 关键服务状态（2026-04-23 审查时）
- FastAPI uvicorn：**运行中**（PID 82520，自 Apr22 起运行）
- `/readiness`：**全绿** — postgres / redis / milvus / embedding / reranker / lmstudio_primary / lmstudio_router 均 healthy
- LM Studio：primary 35B + router qwen3-1.7b 均在线
- Docker 基建：postgres / milvus / redis 运行中（`docker-compose.yml`）
- 模型微服务：BGE-M3 :8001、bce-reranker :8002 运行中（`docker-compose.services.yml`）

### 最新落地的能力（Phase 12 + 12.1 详情）
1. **RAG 评估闭环**（Phase 12）
   - 8 指标：faithfulness / answer_relevancy / context_precision / context_recall / citation_coverage / latency_score / citation_diversity / agent_efficiency
   - LLM-as-judge：默认 router 模型 qwen3-1.7b，可切 primary
   - 10% 在线采样 + 黄金集 batch run
   - 前端：Vue3 `/evaluations` 8 标签页仪表板（`frontend/web/src/views/EvaluationsView.vue`）
   - CLI：`python -m src.evaluation.cli run --golden|--traces [--judge router|primary] [--limit N]`

2. **幻觉抑制闸门**（Phase 12.1）
   - 文件：`src/evaluation/grounding.py`（17 个单测全绿）
   - 两段式校验：
     - **检索质量闸**：引用 <2 / top-1 rerank <0.35 / 均分 <0.25 / 未命中数值占比 >40% → 整段替换为中文拒答模板
     - **数字对齐**：正则提取回答中所有 `<数值 单位>` 事实（30+ 单位族）与 chunk 建索引比对（1% 容差）
   - Early-stop 哨兵：`token_budget_exhausted`、`max_iterations` 直接触发拒答
   - 热配置：`config/settings.yaml::grounding.*`
   - 延迟 <1 ms，失败自动 bypass

3. **BM25 混合检索**（Phase 12）
   - 可插拔：`retrieval.sparse_method: bgem3 | bm25`
   - Milvus 2.5 Function 自动从 `content` 生成 `bm25_vector` 字段

4. **Agent token 预算**
   - `config/settings.yaml::agent.max_total_tokens = 40960`（从 24576 提升）
   - `agent.max_iterations = 6`
   - Agent system prompt 加入 **sql_query 优先** + **STOP RULES**（最多 2 轮、不重复调用）→ `config/prompts/agent_system.txt`

5. **前端 UX 重绘**
   - CitationCard 紧凑 chip（`[n] 《doc》 p.X •` + 三档色点 + tooltip 预览 240 字符）
   - MessageBubble 接入 `marked` + `DOMPurify` + `KaTeX`
   - SSE 按字符分块（修复 `.split()` 吞换行 bug）
   - 认证从内存迁至 PostgreSQL

6. **Early-stop 中文 fallback**
   - `src/agent/orchestrator.py::_early_stop_answer()` 产出 `## 结论 / ## 原因 / ## 建议` 结构化中文消息
   - `src/api/routers/query.py::_apply_grounding()` 透传 `stopped_reason`

### 已知遗留 / 可能的下一步
- **DEV SPEC v5.8 未写**：v5.7 的 changelog 其实已经涵盖了数字对齐 + token bump，所以 v5.8 不是必须的。除非新增能力。
- **前端 `/evaluations` 页面**：未经真实多条 trace 回放验证 UX（等一段在线采样数据）。
- **部署 Phase 8+**：整机部署仍然需要 `docs/DEPLOYMENT_CHECKLIST.md` 走 Phase 0-12。
- **数字对齐单位表扩展**：目前 30+ 单位足够 datasheet 常见场景；碰到 Ω/sr/% 等新单位再加。

### 关键资料索引
| 用途 | 路径 |
|------|------|
| 架构 SSOT | `docs/ENTERPRISE_DEV_SPEC.md` (v5.7) |
| 任务清单 | `docs/DEVELOPMENT_PLAN.md` |
| 两个 AI 的指令同步 | `CLAUDE.md` ⟷ `.github/copilot-instructions.md` |
| 部署手册 | `docs/DEPLOYMENT_CHECKLIST.md` |
| 黄金测试集 | `data/golden_qa.jsonl`（15 条） |
| 评估报告输出 | `reports/eval/` |
| 配置 | `config/settings.yaml` + `config/prompts/*.txt` |
| Trace 日志 | `logs/traces.jsonl` |

---

## 📝 工作日志（按时间倒序追加）

### [Claude] 2026-04-23 — 创建协作工作日志
**目标**：建立 Claude ⟷ Copilot 的共享上下文文档。

**做了什么**：
- 阅读 `git log` / `CLAUDE.md` / `docs/ENTERPRISE_DEV_SPEC.md` changelog / `docs/DEVELOPMENT_PLAN.md` 头部，刷新整个项目的阶段认知。
- 验证环境：`/readiness` 全绿；uvicorn PID 82520 正常；17 个 grounding 单测通过。
- 创建 `WORKLOG.md`（本文档）并写入「项目当前状态快照」作为任何一方接力的起点。
- 清理过期 task（#34–#38 全部标 completed，对应 Phase 12.1 幻觉抑制工作链）。

**下一步建议（给下一个接手的 Agent）**：
1. 下一次被调起时，先读本文件的"最新一条"条目而不是去翻 git log。
2. 每次做任何改动前先写「开始」条目，做完写「结束」条目。
3. 如果用户给新需求，在本文件底部追加 `### [User] 日期 — 需求简述` 条目。

---

### [Copilot] 2026-04-23 — DEVSPEC v5.7 对齐 + GitHub 推送（接力 Claude）
**目标**：用户上一轮在 Claude 没 token 之前留的指令——"阅读 DEVSPEC 全文，与项目对齐，更新到 GitHub"。

**做了什么**：
- 读 `docs/ENTERPRISE_DEV_SPEC.md`（4159 行）关键章节：§3.8 端口、§4.4 目录、§4.8.1 AgentConfig、§6.1/§6.2 阶段表、§7.1 settings.yaml。
- 发现 3 处漂移并修复（commit `11c17af`）：
  - §4.8.1 `AgentConfig`：`max_iterations` 5→**6**，`max_total_tokens` 8192→**40960**（与 Phase 12.1 实际代码一致）。
  - §7.1 `settings.yaml` 同步上述数字 + 注释。
  - §6.1 时间线 ASCII：`Phase 12` → `Phase 12/12.1/12.2`。
  - §6.2 阶段表新增 `Phase 12.1`（4 任务）+ `Phase 12.2`（1 任务，UI 重构）行。
- 推送本地 5 个未上游 commit 到 `https://github.com/CaiLi6/ChipWise-Enterprise.git`：
  - `690146f` Phase 12 + 12.1
  - `43df7aa` 真机集成测试 + golden eval CLI
  - `8c3dcd8` 恢复误删 docs/*.md
  - `638dc2b` 聊天气泡 Vercel/Linear UI 重写
  - `11c17af` DEVSPEC 对齐
  - 推送结果：`d1975b3..11c17af  main -> main` ✅
- 推送鉴权：本机无 credential helper，用 `$GH_TOKEN` 环境变量 + `https://x-access-token:$GH_TOKEN@…` 临时 URL，未写入磁盘。

**改了哪些文件**：
- `docs/ENTERPRISE_DEV_SPEC.md`（+10 / -8 行）

**测试**：仅文档变更，未跑测试。前序 commit 690146f/43df7aa 已在 Claude 那边验证：737 unit + 34 integration_nollm + ruff + mypy + 19 vitest 全绿。

**遗留 / 注意**：
1. WORKLOG.md 是 Claude 在我推送之后创建的，本条是补记——下次工作前先读本文件最末条。
2. 如果再要推送 GitHub，可继续用 `git push "https://x-access-token:${GH_TOKEN}@github.com/CaiLi6/ChipWise-Enterprise.git" main:main`。`origin` 远程 URL 是 https 但无 helper，直接 `git push origin main` 会卡在 `Username:` 提示。
3. DEVSPEC §3.2 model 名字 `qwen3-35b-q5_k_m` / `qwen3-1.7b-q5_k_m` 仅作示例，与实际 LM Studio 加载的 `qwen/qwen3.5-35b-a3b` / `qwen3-1.7b` 不严格一致——spec 已用注释标注"示例"，无需改动。

**下一步建议**：
- 如需让 WORKLOG.md 上 GitHub，把它 git add + commit + push。当前它还是 untracked。

---

### [Claude] 2026-04-23 — 【开始】P0 扩充黄金测试集 15 → 150+
**背景**：上一轮我给出 4 级质量短板清单，用户选择从 P0 动手。目标是把 `data/golden_qa.jsonl` 扩到 150 条以上，按"芯片家族 × 问题类型"分层，用于周度回归对齐 v5.7 基线。

**目标**：
- 扩展后每个 `(chip_family, question_type)` cell 至少 3 条，整体 ≥150 条。
- 保留现有 15 条，不改写。
- 新条目必须对应**系统真实存在**的芯片（否则 grounding 闸门会直接拒答，测不出 RAG 能力）。

**行动计划**（task #39–#43）：
1. 盘点真实数据：PG `chip_params` / Milvus `datasheet_chunks` / Kuzu Chip 节点有多少、覆盖哪些芯片。
2. 读 `src/evaluation/golden.py` 锁定 schema 与现有 15 条的风格。
3. 设计分层矩阵：问题类型（单参数 / 对比 / 选型 / 时序 / 错误处理）× 芯片家族。
4. 生成 JSONL 追加到 `data/golden_qa.jsonl`。
5. 跑 `python -m src.evaluation.cli run --golden --limit 3` 做烟测。

**当前上下文快照**：
- 现有 15 条全部围绕 `PH2A106FLG900` / `XCKU5PFFVD900` 两颗芯片 + PCIe 类问题（见 `data/golden_qa.jsonl`）。覆盖面过窄——只能测 PCIe bandwidth / clock 范围这一类。
- 需要新问题类型覆盖：单参数查询 / 芯片对比 / 选型推荐 / 时序 & 封装 / 错误处理 & errata。

**⚠️ 盘点结果 (task #39 完成)——暴露系统性数据缺失**：

| 存储层 | 状态 | 数据量 |
|-------|------|--------|
| PostgreSQL `chips` / `chip_parameters` / `documents` / `errata` / `design_rules` / `chip_alternatives` | **全部空** | 0 rows |
| PostgreSQL `users` | 1 | (仅 kinglyrex) |
| Milvus `datasheet_chunks` | 119 条（PH2A 98 / DS1101 10 / STM 11） | |
| Milvus `knowledge_notes` | 0 | |
| Kuzu graph | uvicorn 持独占锁，但 PG 空 ⇒ 图必空 | |

**结论**：`sql_query` / `chip_compare` / `graph_query` 三个 Tool 在生产上跑的是空库；当前系统答题能力 ≈ 纯 RAG 从《PH2A106FLG900 兼容指南》98 条 chunks 里 retrieve。

**决策**：用户选择按"最佳路线"继续 → 我执行路线 C：围绕 PH2A106FLG900 1 颗芯片扩 40 条 golden 立起基线，数据入库留新 task #45 追踪。

---

### [Claude] 2026-04-23 — 【结束】P0 黄金集扩充 (15 → 55) + smoke 揭露 3 个新 bug
**结论**：P0 路线 C（我推荐的务实方案）全部完成。选 C 而非 B/A，因为数据入库那条路要半天—一天，用户要"按最佳路线"先把能立起的基线立起来。

**交付**：
- `scripts/expand_golden_p0.py`（新文件）——可重入执行，按 id 去重，40 条基于 PH2A106FLG900 兼容指南 98 chunks 精确 grounded 的 QA。
- `data/golden_qa.jsonl`：15 → **55 条**（append，未改动原 15）。
- 分层：A 单参数数值 14 / B 对比 10 / C Y-N 特性 6 / D 设计规则 6 / E 应拒答 4。
- 覆盖 **20+ 参数族**：PCIe / DSP / PLB / ERAM / ERAM_144K / PLL / HXT / 100G MAC / CONFIG / SEU / DDR / 主频 / 电源 / IO 电平 / IO 驱动 / IO 速率 / 热插拔 / IO BANK / 封装 / 热阻。
- 新 task #45：追踪"数据入库"作为后续——现实是 PG/Kuzu 全空，所以本轮只围绕 1 份文档扩展。
- 新增 MEMORY：`feedback_worklog_protocol.md`（协作协议持久化）。

**Smoke 测试结果**（task #43，直接跑 orchestrator 而非 HTTP，因无 admin 口令）：
| 测试 ID | 类别 | 状态 | 问题 |
|---------|------|------|------|
| `g_p0_dsp_count` | single_param | 跑通但**答错** | GT: DSP=1,800 / 实际答: DSP=715（把 DSP 主频 MHz 当成了数量） |
| `g_p0_cmp_hxt_quad` | compare | 跑通但**空答案** | 2 轮 iter 后 answer=""，citations=0 |
| `g_p0_abstain_price` | abstain | 跑通但**空答案** | 期望结构化拒答，实际 answer=""（拒答模板未注入） |

**Schema / Pipeline 验证**：
- `list_golden()` 解析 55 条全绿，0 schema 违规；新 40 条全部含 8 个必需字段。
- 真实 orchestrator.run() 能消费新 golden，只是**答案质量差**。说明：
  - 扩 golden 成功立起"单芯片深度"回归基线。
  - 原来 15 条 PCIe-only 设计 ≈ 永远不会碰到主频/Quad 数量/拒答这些 corner。

**Smoke 暴露的 3 个真实缺陷（比 golden 扩充本身更有价值）**：
1. **RAG 检索 + 重排把"DSP 主频 715 MHz"召到 top 位，LLM 误读为"DSP 数量 715"** —— 表明 rag chunks 对数字 vs 单位的关联理解缺位。**P0.5**：同 chunk 内多字段（name / number / unit）在召回时需整体呈现，不能只返回数字片段。
2. **HXT Quad 对比返回空串** —— 可能 grounding retrieval gate 把低分召回替换成空，而不是拒答模板。需要 debug `_apply_grounding()` 是否在某条路径上写回 `""` 而非 abstain 字符串。
3. **拒答类问题直接空答** —— 同样指向 grounding 注入失败。需要看 `annotate_answer()` 的 `abstain_replaces_answer` 路径有没有真正挂进 query router 的响应链。

**Kuzu lock 噪声**：uvicorn 持有 `data/kuzu` 独占锁，导致独立 Python 进程启动 orchestrator 时 `GraphQueryTool` 实例化失败（只影响 graph 工具，rag/sql 仍可用）。生产里只有 uvicorn 一家访问，不是问题；但本地调试脚本要避免并发实例化图库。

**改了哪些文件**：
- `data/golden_qa.jsonl` (+40 行 append)
- `scripts/expand_golden_p0.py` (新建, 180 行)

**给下一个接手者的关键提示**：
1. 55 条 golden 里只有 14 条引用 `XCKU5PFFVD900`（B 对比类）；余下 41 条是单芯片问题。做周度回归时 XCKU 答案也会走 RAG 同一份文档。
2. 如果要扩到 150+，必须先 **完成 task #45（数据入库）**。现在硬扩只会堆砌拒答。
3. Smoke 暴露的 3 个 bug 比 golden 本身更值得立刻修——尤其是 bug #3 (拒答空串)，直接把"安全"变成"沉默"。
4. 运行完整回归：`.venv/bin/python -m src.evaluation.cli run --golden`（55 条串行，约 15-20 分钟，会打到 primary 35B）。先不要跑，等把 3 个 bug 修完再做基线。

---

### [Claude] 2026-04-23 — 【开始】Bug#3/#2 修复：拒答+对比返回空串
**RAG/Agent 专家判断**：P0 smoke 暴露的 3 个 bug 里，#3（拒答返回空串）和 #2（HXT Quad 对比返回空串）大概率**同根**——都是 `answer == ""` 从回退链路漏出。

**优先级排序理由**：
- Bug #3 是安全回退断裂：grounding 应该"不确定时说'不确定'"，现在说空字符串——用户看到的是"系统坏了"，比答错更糟。
- 同根修复 ROI 最高；推迟到后面还得重测。
- **现在跑基线会污染数据**：Bug 3 会把 4 条 abstain + N 条 compare 的 faithfulness/relevancy 判 0，测完要重测。
- Bug #1（DSP 主频当数量）是 RAG 深度问题（chunk 格式 + prompt + 重排协同），周期长，留第二攻。

**行动计划**（task #46-#48）：
1. 读 `src/evaluation/grounding.py`（abstain 分支 + annotate_answer）和 `src/api/routers/query.py::_apply_grounding()`。
2. 用独立脚本复现：直接输入 `answer=""` / 低分引用，看 grounding 返回什么。
3. 修复 + 加单测覆盖"agent 返回空串时必须进入 abstain 模板"这条路径。
4. 重跑 smoke 三条确认。

---

### [Claude] 2026-04-23 — 【结束】Bug#3/#2 复诊：**不是 bug，是我 smoke 的姿势错了**
**核心结论**：Bug #3 和 #2 **不存在**。我之前的 smoke 直接调 `orchestrator.run()`，**绕过了 `_apply_grounding()`**。把 HTTP 链路复现后，grounding 表现完全正确。

**诊断脚本复现（orchestrator.run() + 手动调 `check_grounding` + `annotate_answer`，模拟 query router 真实路径）**：

| QID | answer 长度 | citations | check_grounding | annotate 后 |
|-----|------------|-----------|-----------------|-------------|
| `g_p0_dsp_count` | 397 字（含 "715 DSP" 错答） | 5, top=0.534 | `abstain=True` / 2/4 数值无引用 | ✅ 替换成 108 字拒答模板 |
| `g_p0_cmp_hxt_quad` | **0 字** | 0 | `abstain=True` / 仅 0 条引用 | ✅ 注入 108 字拒答模板 |
| `g_p0_abstain_price` | 838 字（LLM 自己拒答，"无法提供单价…"） | 5, top=0.496 | `abstain=False` | ✅ 原样透传（本该如此）|

**判决**：
- HTTP 路径下，用户**永远不会看到空串**——grounding 检测到 `len(citations) < 2` 或数值对不上就强制抹成拒答模板。
- 之前表格里的"空答案"是 orchestrator 原始返回，不是用户看到的东西。
- task #46 / #47 / #48 全部关闭（**no bug; smoke was flawed**）。

**仍然真实的问题（只剩 Bug #1）**：
- DSP 数量被答成 715（主频 MHz 值）。grounding 能抓住并拒答（用户不会看到错答），但 **abstain 率会被虚高**——影响指标真实度。
- 根因：chunk 把"DSP 数量 1,800"和"DSP 最高频率 715 MHz"分开了，LLM 在没有锚上下文时抓错。属于 RAG chunk 质量 + prompt 工程问题，不是 grounding 能修的。

**给下一个接手者的关键提示**：
1. **不要再动 grounding** —— 它是对的。
2. **Bug #1 是真 bug**，但优先级可以让：grounding 在用户侧是"拒答而非错答"，体验是合格的。
3. 现在可以放心跑基线：`source .venv/bin/activate && python -m src.evaluation.cli run --golden`（55 条 × ~20s ≈ 15-20 min）。基线数据不会被假 bug 污染。
4. 跑基线时**务必保证 uvicorn 在跑**（grounding 只在 HTTP 路径生效；CLI runner 用的是 HTTP client 还是直调 orchestrator，需要确认 —— 见下一步）。

---

### [Claude] 2026-04-23 — 【开始】确认 eval runner 路径 + 跑 v5.7 基线
**RAG 专家判断**：grounding 确认正确后，下一步的最高价值动作是**冻结 v5.7 基线指标**——之后任何改动（chunk 质量、prompt、重排权重）都能跟这条基线对比，否则优化就是盲调。

**动作**：
1. 读 `src/evaluation/runner.py` / `batch_runner.py`，确认它调的是 HTTP 还是 orchestrator 直连。如果是直连，需要在 runner 里也挂上 `_apply_grounding`，否则 abstain 指标失真。
2. 跑 `python -m src.evaluation.cli run --golden --judge router`（55 条 × router judge，~15 min）。
3. 把结果写进 `reports/eval/` + WORKLOG 记录 8 指标数值，作为 v5.7 基线。

### [Copilot] 2026-04-23 — 【结束】v5.7 基线测得 + grounding 已织入 batch_runner（接力 Claude）
**接力**：Claude 留下 task #49 「确认 eval runner 路径 + 跑 v5.7 基线」处于 **【开始】** 状态。已检查它在工作树里的未提交改动 (`src/evaluation/batch_runner.py` +67/-2，`scripts/expand_golden_p0.py` 新增 +180，`data/golden_qa.jsonl` +40) ——他事实上**已经把 grounding 织进了 batch_runner**（`_build_grounding_config_standalone()` + 对每条样本调 `check_grounding` + `annotate_answer`，并存 `raw_answer` / `grounding` 元数据），只差跑基线。本轮我直接跑完了。

**做了什么**：
- 烟测 `from src.evaluation.batch_runner import _build_grounding_config_standalone` —— 配置加载正常，min_citations=2 / min_top=0.35 / min_mean=0.25。
- 运行 `python -m src.evaluation.cli run --golden --judge router`：
  - 启动 11:05:36 → 完成 11:25:20，耗时 **19 min 44 s**（55 条 × ~21.5s/条）。
  - 0 失败、0 空答（验证 grounding 至少没把答案抹成空串）。
  - GraphQueryTool 仍因 uvicorn 锁 Kuzu 而初始化失败（预期内，与 Claude 笔记一致），8 个 tool 正常工作。
- 落盘：
  - `reports/eval/v5.7_baseline_run.log`（完整 stdout，约 100 KB）
  - `reports/eval/v5.7_baseline_2026-04-23.json`（batch 聚合）

**📊 v5.7 基线（55 条 Golden / qwen3-1.7b judge）**：

| 指标 | 值 | n | 说明 |
|------|-----|----|------|
| `faithfulness` | **0.594** | 34 | 仅评有引用的样本 |
| `answer_relevancy` | **0.411** | 55 | 全样本 |
| `context_precision` | **0.083** | 34 | ⚠️ 极低 — 召回的 chunk 和 GT 重合度差 |
| `context_recall` | **0.482** | 34 | 仅评有引用的样本 |
| `citation_coverage` | **0.509** | 55 | 全样本 |
| **拒答率** | **27/55 = 49.1%** | — | 通过模板文本"暂无法给出可靠答案"统计；`meta.grounding.abstained` 字段全为 False（持久化漏字段，是日志 bug 不是 grounding bug） |
| **失败率 (`answer_relevancy<0.3`)** | **24/55 = 43.6%** | — | 与拒答率高度重合；扩展后的 golden 集打到了 RAG 真实弱区 |

**和 Claude 上一轮 15 条 baseline 对比**：

| 指标 | 15 条 (旧) | 55 条 (新) | Δ |
|------|-----------|-----------|----|
| faithfulness | 0.63 | 0.59 | -0.04 |
| answer_relevancy | 0.70 | 0.41 | **-0.29** |
| context_precision | 0.18 | 0.08 | -0.10 |
| context_recall | 0.52 | 0.48 | -0.04 |
| citation_coverage | 0.87 | 0.51 | **-0.36** |

**判读**：
- relevancy / citation_coverage 大跌完全符合预期 —— 旧 15 条都是 PCIe 相关，命中率天然高；新 40 条覆盖 DSP/PLL/HXT/封装/热阻/IO 等"广角"，RAG 召回深度不足直接显形。
- 拒答率近半 = grounding 闸门工作正常，把"召回不足或数字对不上"的回答替换成中文模板，**把幻觉风险转成了用户可识别的拒答**。
- context_precision 0.08 是真问题：召回的 chunk 大部分跟 ground truth 不在一个语义平面。

**改了哪些文件 / 资产**：
- 已 commit (本轮):
  - `data/golden_qa.jsonl` (+40 条 golden) [Claude 留下的未提交改动，本轮纳入提交]
  - `src/evaluation/batch_runner.py` (grounding 织入) [Claude 留下]
  - `scripts/expand_golden_p0.py` (新文件) [Claude 留下]
  - `reports/eval/v5.7_baseline_2026-04-23.json` (batch 聚合)
  - `reports/eval/v5.7_baseline_run.log` (完整 stdout)
  - `WORKLOG.md` (本条目)

**测试 / 验证**：
- 运行真实 LM Studio 全套 (qwen3-1.7b primary + qwen3-1.7b judge), 真实 Milvus / BGE-M3 / bce-reranker。0 进程崩溃。

**遗留 / 注意**：
1. **batch_runner 持久化漏字段**：`meta.grounding.abstained` 应该被 evaluator 写进 per-sample 记录但没写，得靠匹配模板文本反推。后续应在 `runner.py::_run_samples` 写持久化时把 sample 的 `grounding` dict 透传到 `meta`。**优先级 P2**（数据没丢，只是统计要绕一下）。
2. **GraphQueryTool 在 CLI 模式下永远跑不到** —— 因为 uvicorn 持 Kuzu 锁。任何回归 graph 类问题都需要先 stop uvicorn 再跑 CLI；或者把 batch_runner 改成走 HTTP `/api/v1/evaluations/run`。**优先级 P2**（数据空库，graph 工具暂时也没用武之地）。
3. **真实弱区清单（按 answer_relevancy<0.3 的 24 条）**：DSP 数量、HXT Quad 数量、PLL 输入范围、ERAM_144K 数量、热插拔耐受时长、IO 驱动等级等多参数细分问题。这些就是 P0.5 优化（chunk 质量、prompt 工程、重排权重）的目标清单。
4. **下一步建议（接手 Agent）**：
   - 不要立即扩 golden 到 150+，没有数据入库（task #45）就是堆模板拒答。
   - 真要做的事 = (a) PG/Kuzu 数据入库，(b) 修 chunk 切分让"DSP 数量 1,800 + DSP 主频 715 MHz"在同一段，(c) 在 system prompt 里强化"必须区分参数名/数值/单位"。
   - 再次跑基线前先存这次结果做 baseline-A，下次结果对比。

**给下一个接手者**：v5.7 基线已冻结（`reports/eval/v5.7_baseline_2026-04-23.json`）。任何 RAG/prompt 优化必须能让上述 5 个指标（特别是 context_precision 0.083）显著上升才算有效。

### [Copilot] 2026-04-23 — Gemini 风格前端重设计
**目标**：用户希望 ChipWise 前端在视觉上对齐 Google Gemini（gemini.google.com）的风格——温和的灰底浅色侧边栏、渐变 logo dot、彩色渐变大标题问候语、卡片式建议、胶囊形输入框、悬浮发送按钮。

**改了哪两个核心文件**（commit 见下）：

#### 1. `frontend/web/src/components/AppLayout.vue`（整体重写，275 → 304 行）
- **整侧边栏从深色 (#304156) 切换到 Gemini 暖灰 #f0f4f9**（白底主区域 + 浅灰侧栏的对比，更现代）。
- **品牌行**：ChipWise 字样 + 一颗 8px 蓝→紫→粉渐变圆 dot，对应 Gemini 的 ✦ 标志。
- **新建对话按钮**：`#c2e7ff` Gemini 蓝色填充胶囊，44 px 高、22 px 圆角，悬停加 1 px 阴影。
- **导航栏**：所有菜单项用胶囊形 (border-radius: 999px)，激活态 `#d3e3fd` 浅蓝填充 + #0b57d0 图标色，无左侧蓝条；icon 全部换成 1.8 stroke 的线性 SVG（chat / compare / doc / trace / eval）。
- **历史对话**：胶囊形列表条，激活态浅蓝；删除 ✕ hover 才显示。
- **底部用户区**：32 px 蓝紫渐变头像 + 用户名 + "退出登录" 副文案，整行点击退出，hover 灰底。
- **折叠态**：72 px 宽，所有按钮变正圆。
- 完全移除 Element Plus 的 `el-menu` / `el-button` / `el-aside`（保留全局组件以便其它视图继续用），改成原生 `<nav>` + `<button>`，模板更轻、CSS 完全可控。

#### 2. `frontend/web/src/views/QueryView.vue`（重写，205 → 399 行）
- **Hero 区（空状态）**：
  - 56 px 大字 "你好，{username}"，蓝→紫→粉横向渐变 background-clip: text，真正复刻 Gemini 大问候。
  - 32 px 浅灰副标题 "今天想了解哪颗芯片？"。
  - **背景径向渐变**：3 个柔和的蓝/粉/紫光斑（z-index 0），带来 Gemini 的"未来感"氛围。
- **建议卡片**：4 张 2×2 网格卡（min 220 px），#f0f4f9 灰底，每张含 Emoji 圆形图标 + 标题 + 3 行截断的副本。点击直接填入输入框。Emoji 选用 📈/⚖️/🧩/🔧 + 真实可工作的查询样例（PH2A106FLG900 DSP 数量 / 对比 / 设计规则 / IO 时序）。
- **顶栏**：去掉旧的灰色边框 + 阴影，改为**透明** + "ChipWise RAG ⌄" 模型 pill，hover 灰底圆角，符合 Gemini 顶栏的"几乎不存在"感。
- **输入区（Composer）**：
  - 胶囊形 28 px 圆角，`#f0f4f9` 灰底，focus 时变白 + 2 层阴影。
  - 内部用 `<textarea>` 替代 `el-input`，自动高度 (autoSize)，最大 200 px 后滚动。
  - 发送按钮 40 px 蓝紫渐变圆，hover 上浮 1 px + 大阴影；空输入时变灰；流式中显示自旋。
  - Enter 发送、Shift+Enter 换行。
- **底部小字**："ChipWise 可能会犯错，请核对关键参数" — 复刻 Gemini 的免责提示。
- **响应式**：<640 px 屏 hero 缩到 40/22 px，建议卡变 1×4。

#### 3. `frontend/web/src/components/__tests__/AppLayout.test.ts` — 修测试
- 把 `.el-menu-item` selector 改成 `.nav-item`（侧栏改用原生 button）。

**测试 / 验证**：
- `npx vue-tsc --noEmit` ✅ 无错误。
- `npm run test -- --run`：5 文件 / **19/19 测试全过**。
- `npm run build`：成功，dist 输出 `QueryView-*.js` 330 KB → gzip 102 KB（QueryView 增大约 4 KB，是 Hero CSS + Composer 的成本，可接受）。
- Vite preview server (PID 70234) 仍在 :4173 跑，刷新即可看到新设计。

**和现有 MessageBubble.vue 的协调**：
- MessageBubble 上一轮 (commit 638dc2b) 已按 Vercel/Linear 风格重写——在 Gemini 风格的 hero/composer 之间夹一段 Vercel 风格的对话气泡，实测视觉协调（都是高对比度、白卡 + 极简）。无需重做。

**截图建议**：用户可在 http://localhost:4173/query 看到：
- 进入页 = 大渐变 "你好，xxx" + 4 张建议卡 + 底部胶囊输入。
- 点任一建议卡 → 文字进入输入框 → 回车发送 → MessageBubble 渲染 → hero 消失，进入正常对话流。

**改了哪些文件**：
- `frontend/web/src/components/AppLayout.vue`（重写）
- `frontend/web/src/views/QueryView.vue`（重写）
- `frontend/web/src/components/__tests__/AppLayout.test.ts`（一行 selector 改名）

**遗留 / 注意**：
1. CompareView / DocumentsView / TracesView / EvaluationsView 仍然是旧 Element Plus 风格——它们和新侧栏放一起会有"侧栏现代、内页传统"的对比。如果用户后续要全 Gemini 化，需要逐一重写这 4 个内页（约 1500 行）。
2. 暂未上传字体（Gemini 用 Google Sans）—— 当前用系统 -apple-system stack，效果接近但不完全一致。如要完全对齐可加 `Inter` 或 `Google Sans` web font。
3. 渐变 hero 文字在 Safari < 14 可能不显示（依赖 -webkit-background-clip）—— 主流环境 OK。
4. 暂未做"暗色模式"——Gemini 有，ChipWise 当前所有页都是明色。

### [User] 2026-04-23 — 提问：系统真实运行情况是 agentic agent + graph rag 吗？

### [Copilot] 2026-04-23 — 真实运行模式核查（80 条 trace + 三库行数）
**结论**：架构上是 Agentic + GraphRAG，**运行时只算 Agentic Vector-RAG**——因为知识图谱实际上是空的。

**实测证据**：

1. **Agentic — 真**：80 条 trace 里 Agent 工具调用分布：rag_search=22、sql_query=6、graph_query=5、knowledge_search=1。ReAct 循环、动态选工具、grounding 闸门、早停哨兵全部在跑。
2. **Graph RAG — 假**：
   - PG 行数：`chips`=0 / `chip_parameters`=0 / `errata`=0 / `design_rules`=0 / `chip_alternatives`=0；只有 `documents`=3。
   - Kùzu 图（从 PG 同步）：只剩 3 个 Document 节点，无 Chip / Parameter 节点 / 无边。
   - Agent 每次都试 sql_query / graph_query，但永远空集，最终 fallback rag_search。
3. **Vector RAG — 真**：Milvus `datasheet_chunks`=180 行（PH2A106FLG900 兼容指南 + DS1101 + STM）。这是唯一真在工作的检索通道——也是为什么基线拒答率 49%、context_precision 0.08 的根因。

**根因链**：上传 PDF 的 ingestion 走完了"切片+embed→Milvus"，但**LLM 参数提取（`src/ingestion/parameter_extractor.py`）没把结构化字段写回 PG**。PG 空 ⇒ Kùzu 同步出的图也空 ⇒ Graph RAG 名存实亡。

**升级路径**（按 ROI 排）：
1. 修 ingestion 参数提取，让 PG `chip_parameters` 真的有数据（这就是之前 WORKLOG 里的 task #45）。
2. 触发 PG → Kùzu 同步，建立 Chip→HAS_PARAMETER→Parameter 边。
3. 重跑基线 ——`context_precision` 预期从 0.08 跳到 0.4+，因为 Agent 终于能 `SELECT value FROM chip_parameters WHERE name='DSP数量'` 直击答案，而非从 chunks 猜。

**用户下一步动作**：等用户决定是否立即着手做参数入库链路。

### [User] 2026-04-23 — 指令：执行 GraphRAG 三阶段全部改造（Phase A/B/C）

### [Copilot] 2026-04-23 — 【开始】GraphRAG ingestion 改造（A→B→C→D）
**目标**：把"上传 PDF → Vector RAG only"升级为"上传 PDF → Vector + Schema + Graph 三库齐全"。

**关键架构决策**：
- **不修复 Celery chain 那 5 个空壳**——它从未被实际使用。前端按"Ingest"按钮走的是 `documents.py::_ingest_one()` 这条同步路径。
- **改造 `_ingest_one()` 直接做满全套**：PG chips insert → 表抽取 → LLM 参数提取 → 设计规则 → 勘误 → 替代品 → Kùzu 同步。
- **复用 uvicorn 进程内已有的 KuzuGraphStore**（避免锁竞争）：通过 app.state 单例。

**Phase 排期**（按依赖图）：
- A0 修 GraphSynchronizer 字段名映射（PG `chips.id` → Kùzu `chip_id` 等）
- A1 _ingest_one 真插 chips 表（替换 CHIP_ID_OFFSET hack）
- A2 表抽取 + LLM 参数提取 → chip_parameters
- A4 Kùzu 共享单例（避免锁冲突）
- A3 sync_chip 调用 → Kùzu 实节点 + 边
- B1 设计规则抽取 → design_rules
- B2 勘误检测 + 抽取 → errata
- B3 替代芯片 LLM 抽取 → chip_alternatives
- C1 /graph-stats endpoint
- C2 前端 Documents 页显示图谱统计
- D1 端到端验证（重新 ingest 3 个 PDF + Cypher 查询 + Agent E2E）
- D2 提交 push

### [Copilot] 2026-04-23 — 【结束】GraphRAG ingestion 改造（A0–C2 完成，D1 部分验证）

**已完成代码**（11 文件，1 新增迁移）：
- `src/ingestion/graph_sync.py` — 完整重写，PG↔Kùzu 字段名映射对齐（`chips.id`→`Chip.chip_id` 等 9 处不一致全部修正）。
- `src/api/routers/documents.py` — `_ingest_one()` 从 ~150 行扩展到 ~280 行：真正 INSERT 到 `chips` 表（替换 `CHIP_ID_OFFSET=10000+doc_id` 假 ID）、调用 `_store_extracted_params/rules/errata/alternatives`、最后 `_sync_kuzu()`，并写入 `documents.metadata->>'kg_stats'`。新增 `GET /api/v1/documents/{id}/graph-stats` 端点。
- `src/api/dependencies.py` — `get_graph_store()` 模块级单例，让查询路由 + ingestion 共享同一个 Kùzu Database 实例（修复"IO lock"竞争）。
- `src/api/routers/query.py` — orchestrator 初始化改用共享单例。
- `src/core/settings.py` — `LLMSettings` 增加 `extractor: LLMEndpointSettings | None = None`。
- `config/settings.yaml` — 新增 `llm.extractor` 角色（gemma-4-31b-it，timeout=600）。
- `src/ingestion/param_extractor.py` — `_parse_llm_output` 增强（支持 `<think>` 剥离 + 单 JSON 对象兜底），`extract_from_table` 在 LLM 返回空 content 时记日志而非误报"parse failed"。
- `frontend/web/src/api/documents.ts` — 新增 `GraphStats` 接口 + `getGraphStats()` API。
- `frontend/web/src/views/DocumentsView.vue` — 列表页"知识图谱"列展示 5 个彩色 pill（📊params 📐rules ⚠️errata ↔️alt 🕸️Nn·Ee），抽屉详情 6 格 KG 网格。
- `alembic/versions/002_kg_metadata.py` — 新迁移，加 `documents.metadata` JSONB + `uq_chip_parameters_chip_name` 唯一索引。已 `alembic upgrade head` 应用。

**端到端验证结果（D1 部分）**：
- ✅ Migration 应用成功；`vue-tsc` 零错误；`npm run build` 通过；Python 全部 import 干净。
- ✅ uvicorn `/readiness` 7/7 服务就绪（postgres, redis, milvus, embedding, reranker, lmstudio_primary/router）。
- ✅ 上传 3 PDF → ingest 完成 → `chips` 真有 2 行（去重后），`documents.chip_id` FK 设置正确，Kùzu 节点 2-3 个、边 1-2 条/doc。
- ✅ Schema-driven KG 链路全通：PDF 上传时即 `Chip → DESCRIBES ← Document` 关系建立。
- ⚠️ **LLM 参数/规则/勘误/替代品提取未产出数据**（params=0, rules=0, errata=0, alts=0）。

**关键技术发现（耗时最长的调试）**：
1. **qwen3-35b-a3b 是 reasoning 模型**：所有"empty content"的 LLM 调用都是因为 `completion_tokens=4000` 全部消耗在 `reasoning_tokens` 上，从未输出可见 JSON。`/no_think` 前缀 + `chat_template_kwargs.enable_thinking=false` 在 LM Studio 0.3.x 上均无效。
2. **解决方案**：引入第三个 LLM 角色 `extractor`，指向 `gemma-4-31b-it`（非 reasoning），单次 79 token 即可返回干净 JSON。代码已切换 ingestion 使用 extractor 模型。
3. **本机硬件瓶颈**：在 AMD Ryzen AI 395 上 gemma-4-31b 单次 ~1500 token prompt 的 ReadTimeout 仍偶发（即使 600s）。LM Studio JIT 模型切换 + 大表抽取在该硬件上不稳定。

**遗留与下一步**：
- 提取链路代码完整正确，但**完整 ingest 在该机器上耗时不可控**。建议（按 ROI 排）：
  1. **拆细 LLM 调用**：每个表分页批，单次 prompt < 800 tokens；
  2. **用 LM Studio 的结构化输出 JSON Schema 模式**（response_format），强制非 reasoning 路径；
  3. **降级到 7B 抽取模型**（如 gemma-2-9b-it 或 qwen2.5-7b-instruct）；
  4. **后台异步**：把抽取链改回 Celery `heavy` 队列，不阻塞用户上传。
- `WORKLOG.md` 中之前 Claude 提的 evaluation baseline 重跑，等参数入库稳定后再做。

**已提交并推送**：见后续 commit。

**最终提交**：`5ddc284 feat(ingestion): wire schema-driven GraphRAG into upload pipeline`，已推 origin/main。


### [Copilot] 2026-04-23 — 【二次修复】Grounding Gate 过严 + 多芯片识别缺失

**用户反馈**：3 次真实查询暴露 2 个体验问题：
1. `XCKU5PFFVD900 PCIe 用户时钟频率范围` → 0 引用 abstain（实际 doc 2 含此芯片对比内容）
2. `PH2A106FLG900 速率等级` → 答案正确但 grounding 把 `~1, ~2, ~4, ~8`、`2800 Mbps` 等近似/表格碎片当幻觉，触发 `7/17 数值无依据` abstain

**修复**：
- `src/evaluation/grounding.py`：
  - 新增 `_APPROX_RE` + `_TABLE_FRAGMENT_RE`，extract_numeric_facts 跳过 `≈ ~ 约` 前缀和 `~1` 类表格碎片
  - `RetrievalGateConfig.max_unsupported_ratio: 0.40 → 0.60`，`min_unsupported_count: 5`（双门槛，避免单点误判）
  - abstain 触发改要求 `total >= 5`（之前 3）
- `src/api/routers/documents.py`：新增 `_store_co_mentioned_chips()`，扫描全文中其它出现 ≥3 次的芯片型号，自动建 Chip 行 + chip_alternatives 'comention' 边。这样 doc "PH2A106FLG900 vs XCKU5PFFVD900" 上传后 XCKU5PFFVD900 也会被注册为可检索芯片
- `tests/unit/eval/test_grounding.py`：补 1 个 approximate-value test，更新 abstain 测试匹配新双门槛

**验证**：22/22 grounding 测试通过；ruff 0 报错；uvicorn 重启后 7/7 服务就绪。

**遗留**：现有 3 篇文档需要重新 ingest 才能让 co-mentioned chips 落库。代码已就绪，等用户在前端点 "Re-ingest" 即可。

### [Copilot] 2026-04-24 — 系统差距清单 + P1/P2 修复

回答用户"系统现在完美吗" → 不完美，列出 13 项差距（详见对话记录）。立刻执行优先级最高的两项：

**P1: rag_search 接入 co-mention 反向扩展** (`src/agent/tools/rag_search.py`)
- 当 `part_number` 过滤后命中数 < `top_k`，自动追加一次去掉 `part_number` 的宽搜，去重合并后送 reranker
- 配合上一轮 ingestion 的 `_store_co_mentioned_chips`，彻底解决"对比 doc 中提及的芯片查询返回 0 引用"问题
- 测试 `test_search_with_filters` 同步更新为只断言首次调用过滤器

**P2: agent_system 提示词加严"禁止编造数值"** (`config/prompts/agent_system.txt`)
- 新增 "Numeric grounding rules — CRITICAL"：所有带单位数值必须在工具结果中出现；近似值用 `约/≈` 而非 `~`；带宽换算除非源文档明写否则不输出
- 配合上一轮 grounding gate 放宽，从两端共同治理 Q1 那种 "LLM 凭常识补 ~2 GB/s" 问题

**验证**：34/34 测试通过（rag_search 12 + grounding 22）；ruff 0；uvicorn 重启 7/7 就绪。

**剩余 roadmap**（按优先级）：
1. SSE 流式接入 Vue3 前端（已有 endpoint，前端未用）
2. PDF 引用页内高亮跳转
3. LLM 参数抽取实际跑通（换 prompt 或换非-reasoning 模型）
4. PaddleOCR 路径真实验证
5. eval batches 异步堆积无人看 → 接 Prometheus + Grafana
6. e2e smoke CI
7. Query-type 自适应混排权重
8. abstain reason 文案对用户更友好
9. WORKLOG 归档机制
10. follow-up 共指消解（router 模型重写 query）
11. co-mention 阈值按 doc 长度归一化

### [Copilot] 2026-04-24 — 第 3 轮深度优化（6 项 roadmap 一次性收口）

回答用户"持续优化直到完美"。从上轮列出的 11 项 roadmap 中挑了 6 项可立刻闭环的，全部完成：

1. **abstain-msg**: `grounding.py annotate_answer` 现按 reason 类型给出针对性建议（数值类 / 引用类 / 预算类）+ 在 reason 文末附前 3 个未支撑的具体数值，便于用户定位。
2. **comention-norm**: `_store_co_mentioned_chips` 阈值按 doc 长度分档（≤4k → 2 次，≤30k → 3 次，≤100k → 4 次，更长 → 5 次），避免长 datasheet 误报。
3. **sse-frontend**: 前端 `QueryView.vue` 早已接 `/query/stream`（`streamQuery` from `@/api/query.ts`），核实并标记完成。
4. **pdf-jump**: 新增后端 `GET /api/v1/documents/{id}/file`（FileResponse 流式）+ 前端 `CitationCard.vue` 引用 chip 现在是可点击 link，打开 `…/file#page=N` 浏览器原生 PDF viewer 自动跳页。已在 doc_id=9 实测 200 OK + 874KB PDF。
5. **e2e-smoke**: 新增 `tests/unit/test_query_smoke_e2e.py`，TestClient + dependency_overrides 注入 stub orchestrator + UserInfo，全程不依赖 LM Studio/PG/Milvus 即可验证 `/api/v1/query` 完整链路（agent → grounding → response）。CI 友好。
6. **llm-extract-fix**: `param_extraction.txt` 加 few-shot 示例 + 显式空表回退 `[]`；`param_extractor.py` `max_tokens` 4000 → 8000（让 qwen3 reasoning 的 `<think>` 块有空间），新增"0 params 时追加禁 think 重试"。同时把 `.format()` 改为 `.replace()` 避免 JSON 大括号冲突。

**附带修复**: `tests/unit/test_graph_sync.py` 的两个 fixture 用错 column 名（`chip_id`/`param_id` 应为 `id`），导致 `test_sync_chip_basic` / `test_sync_with_params` 长期红色—顺手修了。

**验证**: 
- 740 unit tests pass / 7 skipped（之前 738 pass + 2 fail）
- ruff 0 报错
- 前端 `npm run build` 通过
- uvicorn 重启 7/7 ready，PDF 文件流端点 200 OK 实测

**仍剩 5 项 roadmap**（按价值排序）：
- LLM 参数抽取真实跑通验证（需要触发一次 ingest，hardware 慢）
- PaddleOCR 实跑（需扫描件样本）
- Prometheus + Grafana 仪表盘
- query-type 自适应混排权重
- follow-up 共指消解（router 模型改写 query）

---

## 2026-04-22 23:30 — Copilot · 芯片对比页全面重构

**用户反馈**: 芯片对比页"有点鸡肋"——前端写死 5 个假芯片，后端返回的 LLM 智能解读和引用全被丢弃，字段名也对不上 (`chips` vs `chip_names`、`parameters` vs `comparison_table`)。

### 修复内容

1. **新增后端端点 `GET /api/v1/chips`** (`src/api/routers/chips.py`)
   - 支持 `?q=` 子串搜索 + `?limit=` 分页
   - 返回 `{chip_id, part_number, manufacturer, family, status, param_count}`
   - `param_count DESC, part_number ASC` 排序，参数最丰富的优先
   - 当 db_pool 不可用时优雅返回 `{chips:[], total:0}`
   - 注册进 `src/api/main.py`

2. **前端类型对齐** (`frontend/web/src/types/api.ts`)
   - `CompareRequest`: `chips` → `chip_names`，新增 `dimensions?: string[]`
   - `CompareResult`: 改为 `{chips, comparison_table, analysis, citations}` 与后端一致
   - 新增 `CompareCellValue` (typ/min/max/unit/category) 和 `ChipListItem` 类型

3. **API 层瘦身** (`frontend/web/src/api/compare.ts`)
   - 删除整段 MOCK_PARAMS（约 60 行假数据）
   - `compareChips()` 真实 POST `chip_names`
   - 新增 `listChips(q, limit)`

4. **CompareView.vue 完全重写** (12.8 KB)
   - 删除 `MOCK_CHIPS` 写死数据
   - 替换为 `el-select remote` 远程搜索，下拉显示厂商 + 参数数
   - 新增 **"AI 智能解读"** 卡片：渲染后端 LLM `analysis` (marked + DOMPurify)
   - **按参数类别分组** (electrical/timing/thermal/...)，每组独立 `el-table`
   - **维度过滤器**：可勾选只看电气/时序等
   - **差异高亮** + **类别分组**两个开关
   - 列头芯片名旁加 ✕ 一键移除
   - 单元格智能格式化 `typ unit` (来源 CompareCellValue)
   - 底部用现成 `<CitationCard>` 排版引用，可点击跳转 PDF
   - **导出 Markdown** 按钮：客户端拼装报告 (元信息 + AI 解读 + 表格 + 引用) 触发下载

### 验证

- ruff + mypy: ✅ 通过
- 740/7 单元测试全绿
- frontend `npm run build` 成功 (CompareView chunk 7.44 KB → gzip 3.38 KB)
- uvicorn 重启后实测 `curl /api/v1/chips?limit=5`：返回真实 3 颗芯片 (PH2A106FLG900 / DS1101 / XCKU5PFFVD900) 正确按参数数排序

### 仍可后续优化

- 利用 `chip_alternatives` 边推荐"建议对比"组合
- AI 解读支持流式 (现在仍一次性)

---

## 2026-04-24 03:00 — Copilot · 修复 Agent token 预算频繁耗尽

**用户反馈**: 多次提问命中 "Agent 在检索过程中用尽了 token 预算" 提示，应答失败。

### 根因

`AgentOrchestrator` 把每轮 LLM `total_tokens` 累加到 `TokenBudget(40960)`。
RAG 工具返回的 chunk 全文被原样拼回下一轮 prompt → 输入 token 滚雪球 → 2-3 轮即吃满 4 万。

### 修复

1. **预算翻 4 倍**: `config/settings.yaml` `agent.max_total_tokens` 40960 → **131072**
2. **截断 Tool Observation**: 新增 `agent.max_observation_chars: 4000`
   - `src/agent/orchestrator.py` 在拼回 tool result 时按字符上限截断（保留前 4000 字符 + 提示尾标）
   - `src/core/settings.py` `AgentSettings` + `src/api/routers/query.py` `AgentConfig` 同步加字段
   - 引用全文不需要进 LLM 上下文：`ResponseBuilder` 单独装配 citations
3. `llm.primary.max_tokens` 暂保持 4096（推理模型需要给思考留空间，不动）

### 验证

- ruff/mypy: ✅
- 740/7 单元测试全绿
- uvicorn 重启 7s ready，readiness 返回 degraded（仅 redis 鉴权问题，与本次无关）

### 用户后续如再遇到

可手工调高 `config/settings.yaml`:
- `agent.max_total_tokens` 翻倍
- `retrieval.top_k_search` / `top_k_rerank` 调小
- `agent.max_observation_chars` 调小（如 2000）

---

## 2026-04-24 03:14 — Copilot · 补全 CI/CD 全链路

**用户需求**: "需要整个系统有完整的 CI/CD，CD 简单点也行"。

### 之前现状
CI 已有 4 个 workflow（lint / backend-test / frontend / security-scan），CD 缺失。

### 本次新增

1. **`.github/workflows/release.yml`** — push 到 main 自动构建并发布镜像到 GHCR
   - matrix 构建 3 个镜像：`api` / `celery` / `web`
   - 每个镜像打 3 个 tag：`latest` + `<7位sha>` + `sha-<full>`
   - GHA cache (gha scope) 加速 Docker 层
   - 自动跳过 docs-only 改动（paths-ignore）
   - 用 GITHUB_TOKEN 登录 ghcr.io，无需额外 secret
   - Job summary 输出 `docker pull` 命令方便人工复制

2. **`scripts/deploy.sh`** — 单机 CD 脚本
   - `git pull` → `docker pull` 三个镜像 → `docker compose up -d --no-deps` 仅滚动应用层（PG/Milvus/Redis 不动）→ 60s 内轮询 `/readiness` 验证
   - 支持 `DRY_RUN=1` 预演（已实测打印计划正确）
   - 自动从 `git remote` 推断 `IMAGE_REPO`，可用 env 覆盖
   - 用法：`scripts/deploy.sh 6f83590` 或 `scripts/deploy.sh latest`

3. **`.github/workflows/deploy.yml`** — 手动触发 CD（workflow_dispatch）
   - 依赖 self-hosted runner（label `chipwise-prod`），在生产机上注册一次即可
   - 输入 `tag` + `skip_pull` 两个参数
   - `concurrency: deploy-prod` 防止并发部署
   - 包含 setup 注释，用户照做即可

### 验证

- 4 个 workflow 全部 yaml 语法正确（python yaml.safe_load）
- `DRY_RUN=1 scripts/deploy.sh` 实测：
  - 正确推导 IMAGE_REPO=`ghcr.io/caili6/chipwise-enterprise`
  - 正确识别所有 6 个 app service（api + 4 celery + frontend-web）
  - 真实 curl /readiness 返回 200 (degraded，仅 redis 鉴权)
- 既有 ruff/test workflow 不受影响

### 用户使用流程

**自动 CI**: 任何 push/PR → lint + test + frontend + security 自动跑（已有）
**自动 release**: push 到 main → release.yml 自动 build + push 镜像到 GHCR
**手动 deploy**:
- 方式 A（带 self-hosted runner）：在 GitHub UI 点 "Run workflow" → 选 tag → 等绿
- 方式 B（无 runner）：在生产机执行 `bash scripts/deploy.sh latest`

### 后续可选增强

- 加 staging 环境 workflow（push develop → deploy staging）
- 蓝绿/金丝雀部署（compose scale + nginx 切流）
- Deploy 失败自动回滚到上一个 sha tag

---

## 2026-04-24 03:25 — Copilot · 修复 grounding 误报（"**: 1." 等乱码 fact）

**用户反馈**: "PH2A106FLG900 和 XCKU5PFFVD900 是什么" 这类定义/对比题被强制 abstain，
未支持 fact 显示为 `**: 1.`、`* | 0.`、`) | 0.` —— 明显是乱码。

### 根因

`src/evaluation/grounding.py::extract_numeric_facts` 的 bug：
- 在 `norm = _normalize(text)` 后正则匹配
- `_normalize` 会折叠 `Mb /s` → `mb/s`（`re.sub(r"\s*/\s*", "/", text)`），
  导致 norm 比 text 短若干字符
- 然后 `text[m.start():m.end()]` 用 norm 的偏移切原始 text → **错位切片**
- 切出来的就是 `**: 1.`、`* | 0.` 等 markdown 表格碎片
- 这些碎片永远在 chunk 里找不到 → unsupported_ratio 直接爆 → abstain

### 修复

`src/evaluation/grounding.py`:
1. `raw_slice = m.group(0).strip()` 取**正则匹配本身**，永远是 `<数字><单位>` 形态
2. 新增 `_VALID_RAW_RE = re.compile(r"\d.*?[a-zA-Zμ°%]")` 二次过滤：raw 必须包含数字 + 字母/百分号

`tests/unit/eval/test_grounding.py`: 新增两条回归测试：
- 含 `Mb /s` 的样本不再产生包含 `**`、`* |`、`) |`、`| ` 的 raw
- 列表序号 `1.` / `0.`（无单位）不会被错误抽取

### 验证

- ruff: ✅
- 24/24 grounding 测试通过（22 旧 + 2 新）
- 真实样本验证：
  ```
  '26.6 gb/s' 26.6 gbps
  '0.9 v' 0.9 v
  '300 mhz' 300.0 mhz
  ```
  全部干净，无乱码

### 用户后续效果

之前定义/对比题因乱码 fact 误报 abstain → 修复后正常给答案 + 引用，
仅在真有未支持的数值时才警告。

---

## 2026-04-24 03:55 — Copilot · grounding 默认改为 warn 模式（不再误杀定义/对比题）

**用户反馈**: "PH2A106FLG900 和 XCKU5PFFVD900 是什么" 仍被 abstain。
本次乱码片段已无（上一轮修复生效），但 8/18 个数值（如 0.85V、0.9V、1.0mm）找不到引用，
触发 44% > 40% 阈值，**整段答案被丢弃**。

### 问题分析

定义/对比类问题答案天然包含很多规格数值。grounding 严格逐字匹配数字+单位，
chunk 里写 "0.85V"、答案写 "0.85 V"、或 LLM 对 XCKU5PFFVD900（Xilinx FPGA）
援引了通用知识但用户只上传了 PH2A 的 datasheet → 部分数值找不到很正常。

把整段答案替换成 "暂无法给出可靠答案" 是过度反应：
- 已经有 8 条引用
- 检索分数正常
- 答案主体（架构、定位、差异）都对

### 修复

引入 `numeric_abstain_mode: "warn" | "hard"`（默认 `warn`）：

| 模式 | 行为 |
|---|---|
| `warn` (默认) | 保留 LLM 答案，顶部加 `> ⚠️ 未在引用材料中找到数值: ...` 横幅 |
| `hard` (旧行为) | 替换答案为 abstain 模板 |

**关键**: 检索质量失败（无引用 / 分数过低）和 early-stop 失败仍 hard-abstain，
因为那种情况答案本身不可信。数值 grounding 是**纠错信号**而非**杀手**。

### 改动

- `src/evaluation/grounding.py`:
  - `RetrievalGateConfig` 新增 `numeric_abstain_mode: str = "warn"`
  - `check_grounding()` 仅在 mode=="hard" 时设 abstain=True
- `src/api/routers/query.py` + `src/evaluation/batch_runner.py`: 透传新字段
- `config/settings.yaml`: 默认 `numeric_abstain_mode: "warn"`
- `tests/unit/eval/test_grounding.py`:
  - 旧 `test_abstain_on_too_many_unsupported` 显式传 `numeric_abstain_mode="hard"`
  - 新增 `test_warn_mode_keeps_answer_on_numeric_failure` 覆盖默认行为

### 验证

- ruff ✅ / 25/25 grounding 测试通过
- uvicorn 重启加载新配置

### 用户可调

如果未来想恢复严苛行为，把 `config/settings.yaml`:
```yaml
grounding:
  numeric_abstain_mode: "hard"
```

---

## 2026-04-24 04:55 — Copilot · 修复严重隐私 bug：跨用户共享会话历史

**用户反馈**: 用不同账号登录看到的"最近对话"是同一份 → 隐私泄漏。

### 根因

`frontend/web/src/stores/query.ts` 用 **全局 localStorage key**：
- `chipwise_sessions_v1`
- `chipwise_current_session`

无任何用户隔离。logout 也不清理。
所以同一浏览器：A 登出后 → B 登入 → B 直接看到 A 的全部对话和提问。

⚠️ 后端是没问题的（Redis key `session:{user_id}:{session_id}` 已按用户隔离），
此 bug 纯前端，但严重程度等同于隐私泄漏。

### 修复

`frontend/web/src/stores/query.ts` 重构：
1. **按用户名分桶**:
   - `chipwise_sessions_v1::<username>`
   - `chipwise_current_session::<username>`
   - 未登录用 `guest` bucket
2. **登入/登出自动切换**: `watch(() => auth.username, ...)` 触发重新加载对应 bucket
3. **取消 pending 持久化**: 切换用户前清掉 debounce 定时器，防止旧用户数据写到新 bucket
4. **一次性 legacy 迁移**: `migrateLegacyKeys()` 把老的全局 key 平移到当前用户的 bucket 然后删除原 key —— 老用户的历史不丢，但其他人也看不到

### 验证

- frontend `npm run build` ✅
- vitest 19/19 通过
- 逻辑：A 登入 → 写到 `chipwise_sessions_v1::A`；A 登出 watcher 触发，sessions 切到 `guest` bucket；B 登入 watcher 触发，sessions 切到 `chipwise_sessions_v1::B`（空或 B 自己的历史）

### 后续可选增强

- 用 user_id 而非 username 作 bucket key（避免改名场景）
- "退出登录"按钮可加二级确认 + "清除本机历史"选项（彻底删 bucket）
- 会话历史改为后端持久化（PG `conversations` 表已有 schema），跨设备同步

---

## 2026-04-22 · GitHub Copilot · 登录/注册页 UI 大改版

**问题**: 用户反馈登录页"太普通"，希望对标市面上 UI 做得最好的公司（Linear / Vercel / Stripe / Notion）。

**改动**:

- 重写 `frontend/web/src/views/LoginView.vue` 与 `RegisterView.vue` 为 **左右分屏式现代认证页**。
- **左侧 Brand 面板**（Linear 风格）：
  - 深色径向渐变底 (`#1a1f3a → #050610`)
  - 三颗动态发光球体 (`orb-a/b/c`)，18s 浮动动画
  - 网格遮罩（径向 mask）增加纵深感
  - 大标题 + 渐变文字（紫蓝青）+ 三条产品卖点
- **右侧表单面板**（Vercel 风格）：
  - 极简白底，原生 `<input>` 替换 el-input（更精致的 focus ring）
  - 黑色主按钮 + spinner，hover 微动画
  - 密码显示切换、行内错误提示、`fade` 过渡
  - SSO 按钮改为 3 列 icon+文字组合，hover 变品牌色
- 注册页同款风格 + 实时校验（用户名 / 密码 / 确认 / 邮箱）+ 邮箱/部门双列布局。
- 响应式：< 980px 自动隐藏左侧 Brand 面板。

**验证**:
- `npm run build` 清晰通过（LoginView 5.97 KB / RegisterView 6.75 KB）
- `npx vitest run` 19/19 全部通过
- 不依赖任何新 npm 包，纯 CSS 实现动效

**Commit**: 见下方 git log。

