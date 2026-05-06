# FT-ICR MS Web 分析平台

基于 FastAPI + Vue 3 的 FT-ICR MS 数据分析平台，支持常规分析、DPR 数据分析、批量处理、分子数据库创建与对比、机器学习和 SHAP 分析。

## 功能

- 原始质谱数据常规分析、历史记录管理和结果导出
- 常规分析 CSV 导入补齐指标列
- 批量上传常规分析 CSV，批量生成 Van Krevelen 图、PDF ZIP 和加权平均 Excel
- DPR 数据分析、DPR 图和热图导出
- 分子数据库创建、追加、删除、下载和样品对比
- PMD 单样本/双样本反应网络分析，支持 GraphML/GEXF、反应统计 CSV、雷达图 PDF，并支持默认反应或自定义反应
- XGBoost 机器学习分析，支持二分类/三分类
- SHAP 二分类/三分类解释，支持选择解释类别和 SHAP 数据集
- 中英文界面切换，默认英文

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
http://<server-ip>:8080
```

Docker 默认将前端暴露到服务器 `8080` 端口，即 `8080:80`。如果 8080 被占用，可以修改 `deploy/docker-compose.yml` 里的端口映射。

如果你用宝塔/1Panel/Nginx 做反向代理，建议代理到：

```text
http://127.0.0.1:8080
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

如果服务器提示 `Your local changes to the following files would be overwritten by merge`，通常是服务器上临时修改过部署文件。确认不需要保留服务器本地改动时，可执行：

```bash
cd ~/FT-ICR-MS
git restore deploy/deploy.sh deploy/docker-compose.yml
git pull
cd deploy
docker compose up -d --build
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

## 服务器字体

Docker 镜像会自动安装 Times 兼容字体和 Noto CJK 字体，避免 Linux 服务器生成图表时退回默认字体或中文显示方框。

真正的 Times New Roman 属于微软字体，仓库不会直接携带。若需要服务器输出完全等同 Windows 的 Times New Roman，请将合法授权的 `times.ttf`、`timesbd.ttf`、`timesi.ttf`、`timesbi.ttf` 放入 `backend/app/fonts/` 后重新构建 Docker。没有这些字体时，系统会优先使用 Tinos/Liberation Serif 作为 Times New Roman 的 Linux 替代字体。

## PMD 分析说明

PMD 页面里的“质量匹配小数位 / Mass decimals”用于控制反应质量差匹配精度。例如默认值 `8` 表示把分子精确质量四舍五入到 8 位小数后，再匹配 `+O`、`-CO2`、`-CH2` 等反应质量差。数值越大匹配越严格，通常保持 `8` 即可。

PMD 默认反应包含：

- Carboxylic acid：`-CO`、`-CO2`、`-CH2O`
- Oxygen addition：`+O`、`+O2`、`+O3`、`+H2O`、`+H2O2`
- Other reactions：`-H2O`、`+H2`、`-H2`
- Sulfate：`-S`、`-SO`、`-SO2`、`-SO3`
- Amine：`-NH3`、`-NH`
- Dealkyl：`-CH2`、`-C2H2`、`-C2H4`、`-C3H6`

页面支持直接编辑反应分类、正负号、反应式、名称和颜色，也可以新增自定义反应或停用不需要的默认反应。

## 机器学习和 SHAP

机器学习模块使用 XGBoost 分类器。模型始终用训练集训练，页面可选择 SHAP 解释训练集、测试集或全部数据；二分类和三分类都支持选择目标类别。SHAP 正值表示特征把模型输出推向当前选择的目标类别，负值表示远离该目标类别。

SHAP 图、相关性矩阵、混淆矩阵和数据库热图都会调用统一 Matplotlib 字体配置：英文优先 Times New Roman/Tinos/Liberation Serif，中文使用 Noto CJK 等中文字体，避免 Linux 服务器中文方框。

## 目录结构

```text
backend/   FastAPI 后端、分析 pipeline、数据库模型和 API
frontend/  Vue 3 前端；dist 可用于无 Node.js 的服务器部署
deploy/    Docker 和 Linux 部署脚本
```
