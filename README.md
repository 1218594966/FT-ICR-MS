# FT-ICR MS Web 分析平台

基于 FastAPI + Vue 3 的 FT-ICR MS 数据分析平台，支持常规分析、DPR 数据分析、批量处理、分子数据库创建与对比、机器学习和 SHAP 分析。

## 功能

- 原始质谱数据常规分析、历史记录管理和结果导出
- 常规分析 CSV 导入补齐指标列
- 批量上传常规分析 CSV，批量生成 Van Krevelen 图、PDF ZIP 和加权平均 Excel
- DPR 数据分析、DPR 图和热图导出
- 分子数据库创建、追加、删除、下载和样品对比
- XGBoost 机器学习分析
- SHAP 二分类/三分类解释，支持选择解释类别和 SHAP 数据集

## 本地开发

后端：

```bash
cd backend
python -m venv ../.venv
../.venv/bin/pip install -r requirements.txt
../.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

前端：

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

本地访问：

- 前端：http://localhost:3000
- 后端 API：http://localhost:8001
- API 文档：http://localhost:8001/docs

## Linux 服务器一键部署

### 方案 A：Docker 部署

服务器需要安装 Git、Docker 和 Docker Compose。Python、Node、Python 包、前端依赖都由 Docker 自动安装。

```bash
git clone <你的 GitHub 仓库地址> fticrms-web
cd fticrms-web
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

访问：

```text
http://<server-ip>
```

### 方案 B：非 Docker 部署

最低要求：Git、Python 3.10+、python3-venv。

如果服务器有 Node.js/npm，脚本会自动安装前端依赖并重新构建前端；如果没有 npm，则使用仓库中已经构建好的 `frontend/dist`，服务器不需要安装 Node。

```bash
git clone <你的 GitHub 仓库地址> fticrms-web
cd fticrms-web
chmod +x deploy/deploy-linux.sh deploy/stop-linux.sh
PORT=8000 ./deploy/deploy-linux.sh
```

访问：

```text
http://<server-ip>:8000
```

停止：

```bash
./deploy/stop-linux.sh
```

## 常用命令

同步更新到 GitHub：

```bash
git status
git add -A
git commit -m "update"
git push
```

服务器拉取最新版本：

```bash
git pull
PORT=8000 ./deploy/deploy-linux.sh
```

Docker 查看日志：

```bash
docker compose -f deploy/docker-compose.yml logs -f
```

Docker 停止服务：

```bash
docker compose -f deploy/docker-compose.yml down
```

非 Docker 查看日志：

```bash
tail -f logs/server.log logs/server.err.log
```

## 目录结构

```text
backend/   FastAPI 后端、分析 pipeline、数据库模型和 API
frontend/  Vue 3 前端；dist 可用于无 Node.js 的服务器部署
deploy/    Docker 和 Linux 部署脚本
```
