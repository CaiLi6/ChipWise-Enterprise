# ChipWise Enterprise — 芯片数据智能检索与分析平台

## Architecture Design Specification v5.0

| 属性 | 值 |
|------|-----|
| **文档编号** | CW-ARCH-2026-001 |
| **版本** | 5.0.0 |
| **状态** | Approved |
| **作者** | Enterprise AI Architecture Team |
| **审批** | CTO Office |
| **生效日期** | 2026-04-08 |
| **密级** | 内部公开 (Internal) |

---

## 变更记录

| 版本 | 日期 | 变更说明 | 作者 |
|------|------|----------|------|
| 1.0 | 2026-04-07 | 全面重构为企业级架构设计书 | Enterprise AI Architecture Team |
| 2.0 | 2026-04-07 | 企业级 SSO/OIDC 统一认证; Tenacity 指数退避重试; 分布式向量数据库集群; Cloud-Native K8s Helm 部署 & CI/CD 流水线 | Enterprise AI Architecture Team |
| 3.0 | 2026-04-07 | **认知智能架构升级**: Graph RAG (Kùzu 知识图谱); Agentic RAG 编排 (ReAct/Tool Calling Agent Orchestrator); Hybrid + Graph 多路召回; Pipeline → Agent Tools 重构 | Enterprise AI Architecture Team |
| 4.0 | 2026-04-07 | **环境一致性升级**: LLM 推理引擎迁移至 LM Studio; 统一 OpenAI-compatible API; 端口 8000 → 1234; 全链路对齐 | Enterprise AI Architecture Team |
| 5.0 | 2026-04-08 | **文档重构**: 按 7 章中文标题重新组织; 新增「核心特点」概览章; 精简冗余代码; 保留全部架构图与关键表格 | Enterprise AI Architecture Team |

---

## 目录

- [1. 项目概述](#1-项目概述)
- [2. 核心特点](#2-核心特点)
- [3. 技术选型](#3-技术选型)
- [4. 系统架构与模块设计](#4-系统架构与模块设计)
  - [4.1 七层架构总览](#41-七层架构总览)
  - [4.2 在线请求流](#42-在线请求流query-path)
  - [4.3 离线数据流](#43-离线数据流ingestion-path)
  - [4.4 项目目录结构](#44-项目目录结构)
  - [4.5 部署拓扑](#45-部署拓扑)
  - [4.6 数据工程管线](#46-数据工程管线)
  - [4.7 存储 Schema 设计](#47-存储-schema-设计)
  - [4.8 Agent 编排架构](#48-agent-编排架构)
  - [4.9 管线实现](#49-管线实现)
  - [4.10 对话与缓存](#410-对话与缓存)
  - [4.11 并发与容错](#411-并发与容错)
  - [4.12 安全与认证](#412-安全与认证)
- [5. 测试方案与可观测性](#5-测试方案与可观测性)
- [6. 项目排期](#6-项目排期)
- [7. 附录](#7-附录)

---