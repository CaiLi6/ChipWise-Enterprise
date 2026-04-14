# Git & GitHub 项目同步完全指南
## 基于 ChipWise Enterprise 项目

---

## 目录

1. [核心概念](#1-核心概念)
2. [首次推送到 GitHub](#2-首次推送到-github第一次用)
3. [日常更新流程](#3-日常更新流程每次改完代码后)
4. [分支管理](#4-分支管理多功能并行开发)
5. [常见场景处理](#5-常见场景处理)
6. [.gitignore 配置](#6-gitignore-配置哪些文件不要上传)
7. [命令速查表](#7-命令速查表)

---

## 1. 核心概念

把 Git 理解成**游戏存档系统**：

| 游戏 | Git |
|------|-----|
| 手动存档 | `git commit`（提交一个版本快照） |
| 存档记录 | `git log`（查看所有历史提交） |
| 读取存档 | `git checkout`（回到某个版本） |
| 云存档 | GitHub（把本地存档同步到云端） |
| 上传云存档 | `git push` |
| 下载云存档 | `git pull` |

**三个区域**：

```
工作区（Working Tree）     暂存区（Stage/Index）     本地仓库（Repository）     远程（GitHub）
你写代码的地方            准备提交的文件列表          历史提交记录               云端备份
      │                        │                         │                      │
      │──── git add ──────────▶│                         │                      │
      │                        │──── git commit ────────▶│                      │
      │                        │                         │──── git push ────────▶│
      │◀──────────────────────────── git checkout ───────│                      │
      │◀──────────────────────────────────────────────────── git pull ──────────│
```

---

## 2. 首次推送到 GitHub（第一次用）

### 第一步：安装 Git 并配置身份

```bash
# 检查是否已安装
git --version

# 配置你的姓名和邮箱（只需配置一次，所有项目通用）
git config --global user.name "你的名字"
git config --global user.email "你的邮箱@example.com"

# 查看配置
git config --list
```

### 第二步：在 GitHub 创建仓库

1. 登录 [github.com](https://github.com)
2. 点击右上角 **+** → **New repository**
3. 填写仓库名：`ChipWise-Enterprise`
4. 选择 **Private**（私有，推荐）
5. **不要**勾选"Add a README file"（本地已有文件）
6. 点击 **Create repository**

### 第三步：本地初始化并推送

```bash
# 进入项目根目录
cd /home/mech-mind/ChipWise-Enterprise

# 初始化 Git 仓库（只做一次）
git init

# 把所有文件加入暂存区
git add .

# 查看哪些文件要被提交（建议先看一眼）
git status

# 创建第一个提交
git commit -m "初始提交：ChipWise Enterprise v1.0"

# 关联到 GitHub 远程仓库（把下面的 URL 替换成你的）
git remote add origin https://github.com/你的用户名/ChipWise-Enterprise.git

# 推送到 GitHub（第一次用 -u，以后直接 git push 就行）
git push -u origin main
```

### GitHub 身份验证

现在 GitHub 不支持用户名+密码，需要用 **Personal Access Token（PAT）**：

1. GitHub → 右上角头像 → **Settings**
2. 左侧菜单最底部 → **Developer settings**
3. **Personal access tokens** → **Tokens (classic)**
4. **Generate new token** → 选择过期时间 → 勾选 `repo` 权限
5. 生成后**立刻复制**（只显示一次！）
6. push 时，密码输入框填入这个 Token（不是你的 GitHub 密码）

**更省事的方案**（推荐）：用 SSH 密钥，一次配置永久免密：

```bash
# 生成 SSH 密钥
ssh-keygen -t ed25519 -C "你的邮箱@example.com"
# 一路回车即可（默认存到 ~/.ssh/id_ed25519）

# 查看公钥
cat ~/.ssh/id_ed25519.pub

# 把输出的内容复制，粘贴到：
# GitHub → Settings → SSH and GPG keys → New SSH key

# 测试是否成功
ssh -T git@github.com
# 看到 "Hi 你的名字! You've successfully authenticated" 就成功了

# 改用 SSH 方式关联远程
git remote set-url origin git@github.com:你的用户名/ChipWise-Enterprise.git
```

---

## 3. 日常更新流程（每次改完代码后）

这是**最常用的流程**，每次修改项目后按这个步骤操作：

```bash
# 第一步：查看什么发生了变化
git status

# 第二步：查看具体改了什么（可选，检查自己的修改）
git diff

# 第三步：把修改加入暂存区
git add .                   # 把所有改动加入（最常用）
git add src/api/main.py     # 只加某个文件
git add src/                # 只加某个目录

# 第四步：提交（写清楚做了什么）
git commit -m "feat: 添加芯片对比接口"

# 第五步：推送到 GitHub
git push
```

### 提交信息怎么写？

好的提交信息让你几个月后还能看懂做了什么。推荐 **约定式提交（Conventional Commits）** 格式：

```
<类型>: <简短描述>

类型说明：
feat     新功能
fix      修复 bug
docs     文档更新
refactor 重构（不改功能）
test     添加或修改测试
chore    构建、配置、依赖更新
perf     性能优化
```

**实际例子**：

```bash
git commit -m "feat: 新增语义缓存，命中率提升40%"
git commit -m "fix: 修复JWT过期后返回500而非401的问题"
git commit -m "docs: 更新README的部署说明"
git commit -m "chore: 升级 FastAPI 到 0.111.0"
git commit -m "refactor: 重构AgentOrchestrator提高可测试性"
```

❌ **不好的提交信息**：
```bash
git commit -m "改了些东西"
git commit -m "update"
git commit -m "fix bug"
git commit -m "aaa"
```

---

## 4. 分支管理（多功能并行开发）

**分支** = 从主线拉出一条独立的开发线，互不干扰。

```
main（主分支，稳定版本）
  │
  ├── feat/rag-cache（开发语义缓存）
  │        └── 完成后 merge 回 main
  │
  └── fix/jwt-401（修复JWT问题）
           └── 完成后 merge 回 main
```

### 日常分支操作

```bash
# 查看所有分支（* 表示当前分支）
git branch

# 创建并切换到新分支（推荐每个新功能/修复创建单独分支）
git checkout -b feat/semantic-cache

# 在新分支上正常工作...
# git add . && git commit -m "..."

# 推送新分支到 GitHub
git push -u origin feat/semantic-cache

# 完成后，切回 main 分支
git checkout main

# 把功能分支合并进来
git merge feat/semantic-cache

# 推送 main 到 GitHub
git push

# 删除已完成的分支（可选）
git branch -d feat/semantic-cache
git push origin --delete feat/semantic-cache  # 同时删除远程分支
```

### GitHub Pull Request 工作流（团队协作推荐）

```
1. 从 main 创建功能分支：git checkout -b feat/xxx
2. 开发完成，push 到 GitHub
3. 在 GitHub 网页上创建 Pull Request
4. 团队成员 Code Review
5. 审核通过后 Merge 到 main
6. 删除功能分支
```

---

## 5. 常见场景处理

### 场景1：刚改了一堆文件，想看改了什么

```bash
git status          # 哪些文件变了
git diff            # 具体改了什么（未暂存的）
git diff --staged   # 已暂存的改动
```

### 场景2：修改了文件，但想撤销（还未 commit）

```bash
# 撤销某个文件的修改（恢复到上次 commit 的状态）
git checkout -- src/api/main.py

# 撤销所有未提交的修改（危险！不可恢复！）
git checkout -- .

# 只清除暂存区（文件改动保留，但取消 git add）
git reset HEAD src/api/main.py
```

### 场景3：刚 commit 了，但提交信息写错了

```bash
# 修改最近一次 commit 的信息（还没 push 时才能用）
git commit --amend -m "正确的提交信息"
```

### 场景4：想回退到某个历史版本

```bash
# 查看历史提交记录
git log --oneline

# 输出类似：
# a1b2c3d (HEAD -> main) feat: 新增语义缓存
# e4f5g6h fix: 修复JWT问题
# i7j8k9l 初始提交

# 回退到某个版本（会保留文件修改）
git reset --soft a1b2c3d

# 回退到某个版本（完全回退，文件也变回去，危险！）
git reset --hard a1b2c3d

# 更安全的方式：创建一个"回退提交"（推荐生产环境用）
git revert a1b2c3d
```

### 场景5：同事也改了代码，我 pull 时有冲突

```bash
# 拉取远程最新代码
git pull

# 如果有冲突，Git 会标记冲突文件：
# <<<<<<< HEAD
# 你的代码
# =======
# 同事的代码
# >>>>>>> origin/main

# 手动编辑文件，删掉标记，保留正确的代码
# 然后：
git add 冲突文件
git commit -m "resolve: 合并冲突"
git push
```

### 场景6：不小心把密码/密钥 commit 了

**立刻处理，因为即使删除，git 历史里还有记录！**

```bash
# 1. 立刻去 GitHub/LM Studio 撤销那个密钥！
# 2. 从历史中彻底删除（会重写历史，慎用）
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch config/secrets.py" \
  --prune-empty --tag-name-filter cat -- --all

# 3. 强制推送（覆盖远程历史）
git push origin --force --all

# 更好的工具：BFG Repo Cleaner
# https://rtyley.github.io/bfg-repo-cleaner/
```

最好的方案是**预防**：用 `.gitignore` 和环境变量，下一节讲。

### 场景7：误删了文件，想找回来

```bash
# 找到删除文件的那次 commit
git log --all --full-history -- src/api/routers/query.py

# 恢复那个文件
git checkout <commit_hash> -- src/api/routers/query.py
```

### 场景8：在错误的分支上开发了，想移到正确分支

```bash
# 先暂存工作（stash）
git stash

# 切换到正确分支
git checkout feat/correct-branch

# 把暂存的工作取出来
git stash pop
```

---

## 6. .gitignore 配置（哪些文件不要上传）

`.gitignore` 文件告诉 Git 忽略哪些文件，**保护敏感信息，减少仓库体积**。

ChipWise 项目推荐的 `.gitignore`：

```gitignore
# Python 编译文件
__pycache__/
*.py[cod]
*.pyo
*.pyd
.Python

# 虚拟环境（体积大，不要上传）
.venv/
venv/
env/

# 环境变量文件（含密码！绝对不要上传）
.env
.env.local
.env.production
*.env

# 数据库文件
*.db
*.sqlite3
data/kuzu/          # Kùzu 数据目录

# 日志
logs/
*.log

# 模型缓存（几个GB，不上传）
.cache/
models/
*.bin
*.safetensors

# 上传的文档
data/documents/

# 导出的报告
data/exports/

# IDE 文件
.idea/
.vscode/
*.swp

# macOS
.DS_Store

# 测试覆盖率报告
htmlcov/
.coverage
.pytest_cache/

# 构建产物
dist/
build/
*.egg-info/

# Celery 运行时文件
celerybeat-schedule
celerybeat.pid
```

创建或更新 `.gitignore`：
```bash
# 如果文件已被追踪但以后不想跟踪，需要先移出缓存
git rm --cached .env
git rm -r --cached data/kuzu/

# 然后加到 .gitignore，重新 commit
```

---

## 7. 命令速查表

### 最高频使用（每天都用）

```bash
git status                          # 查看当前状态
git add .                           # 暂存所有改动
git commit -m "提交信息"             # 提交
git push                            # 推送到 GitHub
git pull                            # 从 GitHub 拉取最新
git log --oneline                   # 查看简洁的提交历史
```

### 分支操作

```bash
git branch                          # 查看所有分支
git checkout -b 分支名              # 创建并切换分支
git checkout 分支名                 # 切换分支
git merge 分支名                    # 合并分支到当前分支
git branch -d 分支名                # 删除本地分支
```

### 撤销操作

```bash
git checkout -- 文件名              # 撤销文件修改（未暂存）
git reset HEAD 文件名               # 取消暂存（git add 的逆操作）
git commit --amend -m "新信息"      # 修改最近一次提交信息
git revert <commit_hash>            # 安全回退某次提交
git stash / git stash pop           # 临时暂存 / 恢复
```

### 查看信息

```bash
git log --oneline --graph           # 图形化查看分支历史
git diff                            # 查看未暂存的改动
git diff --staged                   # 查看已暂存的改动
git show <commit_hash>              # 查看某次提交的详情
git blame 文件名                    # 查看每行代码是谁写的
git remote -v                       # 查看远程仓库地址
```

---

## 标准更新流程（快速参考）

每次改完代码后，固定执行以下 3 步：

```bash
git add .
git commit -m "feat/fix/docs: 描述你做了什么"
git push
```

就这三条命令，搞定 99% 的日常同步需求。
