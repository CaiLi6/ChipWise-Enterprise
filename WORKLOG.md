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
