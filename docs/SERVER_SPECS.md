# ChipWise Enterprise 服务器配置说明

**文档版本**: 1.0  
**更新日期**: 2026-06-17  
**适用环境**: 极摩客 NucBox EVO-X2 单机部署

---

## 1. GPU 配置

| 项目 | 配置 |
|------|------|
| **GPU 型号** | AMD Radeon 8060S (集成显卡) |
| **架构** | RDNA 3.5 |
| **显存** | 4 GB 专用 VRAM |
| **推理方式** | LM Studio 通过 Vulkan 后端调用 GPU 加速，采用 CPU + GPU 混合卸载策略 |

---

## 2. 服务器资源

### 2.1 硬件配置

| 资源 | 配置 |
|------|------|
| **CPU** | AMD Ryzen AI MAX+ 395 (16 核 32 线程，带 NPU) |
| **内存** | 62 GB (物理机可能更高，WSL2 分配 62 GB) |
| **存储** | NVMe SSD |
| **操作系统** | Windows 11 + WSL2 (Ubuntu 24.04) |
| **部署方式** | 单机本地化部署，零数据外泄 |

### 2.2 内存分布

| 服务 | 内存占用 |
|------|----------|
| LM Studio 主模型 (35B Q5 量化) | ~22 GB |
| LM Studio 路由模型 (1.7B) | ~1.5 GB |
| PostgreSQL | ~4 GB |
| Milvus 向量库 | ~8 GB |
| Redis | ~1 GB |
| Celery Workers ×3 | ~6 GB |
| FastAPI + 其他 | ~2 GB |
| **峰值总计** | **~45 GB** |

**剩余可用内存**: 约 17 GB，为系统和突发负载提供缓冲。

---

## 3. GPU 显存

| 项目 | 说明 |
|------|------|
| **总显存** | 4 GB VRAM |
| **模型加载策略** | 部分层卸载 (Partial Offload) |
| **工作原理** | 部分 Transformer 层在 GPU 运行，其余层在 CPU 运行 |
| **实测推理速度** | 35B 模型约 15 tokens/秒 |

> **注意**: 由于 4 GB 显存无法完全加载 35B 模型 (~22 GB 权重)，LM Studio 自动采用 CPU/GPU 混合推理模式。

---

## 4. 并发能力

### 4.1 系统限制

| 指标 | 限制值 | 说明 |
|------|--------|------|
| **主模型 (35B) 并发** | 2 | 受内存和推理资源限制 |
| **路由模型 (1.7B) 并发** | 10 | 轻量级模型，可承受更高并发 |
| **单用户请求限流** | 30 次/分钟 | 防止单用户占用过多资源 |
| **单用户请求限流** | 500 次/小时 | 长周期限流保护 |
| **设计目标用户数** | 20 人团队 | 内网使用场景 |

### 4.2 性能优化措施

| 措施 | 说明 |
|------|------|
| **语义缓存** | 相似度 > 0.95 的查询直接返回缓存结果 |
| **请求限流** | 基于 Redis 的滑动窗口限流 |
| **LLM 信号量** | 全局并发控制，防止 OOM |
| **Agent 迭代限制** | 最多 6 轮 ReAct 迭代，防止无限循环 |

---

## 5. 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| FastAPI Gateway | 8080 | API 入口 |
| LM Studio | 1234 | LLM 推理服务 |
| BGE-M3 Embedding | 8001 | 向量化服务 |
| BCE Reranker | 8002 | 重排序服务 |
| PostgreSQL | 5432 | 关系型数据库 |
| Milvus | 19530 | 向量数据库 |
| Redis | 6379 | 缓存与消息队列 |
| Gradio Frontend | 7860 | Web 前端 (可选) |

---

## 6. 总结

ChipWise Enterprise 部署在 **单机本地化环境**，核心配置如下：

- **计算**: AMD Ryzen AI MAX+ 395 CPU (16C/32T) + 4 GB 集成 GPU
- **内存**: 62 GB RAM
- **推理**: LM Studio 运行量化 35B 大模型，CPU/GPU 混合推理
- **并发**: 主模型最大 2 并发，支持 20 人团队使用
- **安全**: 所有数据本地处理，零外泄风险

该配置满足企业内网 20 人团队的芯片数据智能检索与分析需求。

---

## 附录：验证命令

```bash
# 检查服务健康状态
curl http://localhost:8080/readiness

# 检查 LM Studio 模型
curl http://localhost:1234/v1/models

# 运行完整健康检查
cd /home/mech-mindai/ChipWise-Enterprise
export $(grep -v '^#' .env | xargs)
source .venv/bin/activate
python scripts/healthcheck.py --local
```
