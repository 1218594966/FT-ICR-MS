# FT-ICR MS Molecular Intelligence Platform

A web-based analytical platform for Fourier transform ion cyclotron resonance mass spectrometry (FT-ICR MS) data. The system integrates molecular formula curation, Van Krevelen visualization, DPR fate analysis, molecular source-database comparison, PMD reaction-network construction, batch processing, and XGBoost-SHAP machine-learning interpretation in a reproducible browser workflow.

The project is designed for research scenarios in dissolved organic matter, environmental molecular characterization, molecular transformation inference, and comparative source analysis. It provides deployable full-stack software with Docker and non-Docker Linux deployment scripts.

## Core Capabilities

- Conventional FT-ICR MS data processing with molecular index completion, filtering, history management, and export.
- Batch processing for multiple conventional analysis files, including synchronized Van Krevelen plots, editable PDF exports, and weighted-average summary tables.
- DPR fate analysis for disappearance, persistence/resistance, and production categories, with DPR-specific plots, heatmaps, and downloadable result files.
- Molecular source-database construction from arbitrary grouped files, with database download, deletion, and sample-to-database comparison.
- Two-sample DPR/database comparison, including D/P/R grouping and chi-square contingency analysis.
- PMD analysis for single-sample and cross-sample putative molecular reaction networks, with customizable reaction dictionaries and GraphML/GEXF export.
- XGBoost machine-learning classification for binary and three-class DPR tasks, trained with GridSearchCV and interpreted by SHAP.
- Editable vector PDF output using embedded TrueType/Type 42 fonts where Matplotlib is used.
- English/Chinese interface switching, light/dark themes, and browser-based operation.

## Analytical Scope

This platform is intended to support molecular-level exploratory analysis and hypothesis generation. The implemented workflows should be interpreted with standard domain caution:

- Van Krevelen and elemental-class plots describe molecular compositional space.
- DPR analysis compares molecular presence/absence patterns between paired samples.
- Source-database comparison quantifies molecular overlap and group-level enrichment rather than proving absolute source attribution.
- PMD networks represent putative formula-difference relationships based on predefined reaction mass differences; edges indicate plausible transformations, not direct experimental proof of reaction occurrence.
- SHAP values explain the trained XGBoost model output and should not be interpreted as causal effects without independent validation.

## Machine Learning Method

The machine-learning module follows a supervised classification workflow:

1. Molecular formulas are parsed into elemental counts and derived ratio features.
2. Numeric molecular descriptors are used as model features.
3. Class labels are read from `NewCol`, supporting binary classification or three-class DPR classification.
4. Data are split into stratified training and test sets.
5. XGBoost is optimized using `GridSearchCV` with accuracy scoring.
6. Independent test-set metrics, training metrics, confusion matrices, correlation matrices, and SHAP plots are generated.

### Non-Docker Deployment

Use this when Docker is not available. The server should provide Git and Python 3.10+. If Node.js/npm is available, the frontend can be rebuilt during deployment; otherwise the committed `frontend/dist` build is served directly.

```bash
#!/bin/bash
set -e

# 1. 安装 Python 虚拟环境支持（避免 ensurepip 错误）
sudo apt update
sudo apt install -y python3.12-venv python3-pip

# 2. 克隆或更新代码仓库
REPO_DIR="$HOME/FT-ICR-MS"
if [ -d "$REPO_DIR" ]; then
  echo "仓库已存在，执行 git pull 更新..."
  cd "$REPO_DIR"
  git pull
else
  echo "克隆仓库..."
  git clone https://gitee.com/xinyuan-xu/FT-ICR-MS.git "$REPO_DIR"
  cd "$REPO_DIR"
fi

# 3. 修复 backend/requirements.txt 中的不兼容包（适配 Python 3.12）
BACKEND_REQ="backend/requirements.txt"
if [ -f "$BACKEND_REQ" ]; then
  echo "正在修复 $BACKEND_REQ 以兼容 Python 3.12..."

  # 备份原文件
  cp "$BACKEND_REQ" "$BACKEND_REQ.bak"

  # 修复 numpy：将固定版本改为兼容 Python 3.12 的范围
  sed -i 's/numpy==1.24.4/numpy>=1.26.0,<2.0.0/g' "$BACKEND_REQ"

  # 修复 pandas：通常 pandas 1.5+ 支持 Python 3.12，推荐使用 2.x
  # 如果原文件写的是 pandas==1.3.5 或类似，这里统一替换为 pandas>=2.1.0
  sed -i 's/pandas==[0-9.]*/pandas>=2.1.0/g' "$BACKEND_REQ"

  echo "✅ 已修复 numpy 和 pandas 版本约束"
else
  echo "⚠️ 未找到 $BACKEND_REQ，跳过修复"
fi

# 4. 赋予脚本执行权限
chmod +x deploy/deploy-linux.sh deploy/stop-linux.sh

# 5. 设置端口并运行部署脚本
export PORT=8000
./deploy/deploy-linux.sh

echo "==========================================="
echo "部署完成！服务运行在端口 $PORT"
echo "==========================================="
```

Default access:

```text
http://<server-ip>:8000
```

Stop the non-Docker service:

```bash
./deploy/stop-linux.sh
```

## Server Update

For Docker deployments:

```bash
cd ~/FT-ICR-MS
git pull
cd deploy
docker compose up -d --build
```

For non-Docker deployments:

```bash
cd ~/FT-ICR-MS
git pull
PORT=8000 ./deploy/deploy-linux.sh
```

If `git pull` reports that local deployment files would be overwritten, and the server-side edits do not need to be preserved:

```bash
cd ~/FT-ICR-MS
git restore deploy/deploy.sh deploy/docker-compose.yml
git pull
cd deploy
docker compose up -d --build
```

## Logs

Docker logs:

```bash
docker compose -f deploy/docker-compose.yml logs -f
```

Non-Docker logs:

```bash
tail -f logs/server.log logs/server.err.log
```

## Fonts and Editable PDF Output

The Docker image installs Times-compatible serif fonts and Noto CJK fonts to avoid missing glyphs on Linux servers. Matplotlib PDF outputs are configured to embed TrueType/Type 42 fonts, making text more likely to remain selectable and editable in professional PDF editors.

Microsoft Times New Roman is not bundled because it is proprietary. To obtain exact Times New Roman output on Linux, place legally licensed font files such as `times.ttf`, `timesbd.ttf`, `timesi.ttf`, and `timesbi.ttf` into:

```text
backend/app/fonts/
```

Then rebuild the deployment.

## Repository Structure

```text
backend/    FastAPI backend, analytical APIs, database models, and processing logic
frontend/   Vue 3 frontend and production build artifacts
deploy/     Docker and Linux deployment scripts
```

## Citation and Research Use

When using this platform in academic work, report the analytical assumptions and parameter settings used in each module. In particular, specify:

- FT-ICR MS preprocessing and filtering criteria.
- Elemental classes included in visualization and batch processing.
- DPR category definitions.
- PMD reaction dictionary and mass matching precision.
- Machine-learning feature set, class labels, train/test split, GridSearchCV parameter grid, cross-validation folds, and evaluation metrics.
- SHAP target class and SHAP explanation dataset.

The platform is intended to make molecular-level workflows reproducible, inspectable, and deployable. Scientific conclusions should be supported by appropriate experimental design, statistical reporting, and domain interpretation.
markdown

## 1. 原始 CoreMS 许可证（BSD 2-Clause）

Copyright (c) Battelle Memorial Institute. 保留所有权利。

在满足以下条件的前提下，允许以源代码和二进制形式（无论修改与否）进行再分发和使用：

源代码的再分发必须保留上述版权声明、本条件列表和下述免责声明。

二进制形式的再分发必须在文档和/或其他随附材料中复制上述版权声明、本条件列表和下述免责声明。

本软件按“原样”提供，版权持有人和贡献者不提供任何明示或暗示的保证，包括但不限于对适销性和特定用途适用性的暗示保证。在任何情况下，版权持有人或贡献者均不对因使用本软件而产生的任何直接、间接、附带、特殊、惩戒性或后果性损害承担责任（包括但不限于采购替代商品或服务、使用损失、数据丢失或业务中断），即使已被告知可能发生此类损害。

Copyright (c) Battelle Memorial Institute. All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

## 2. 本衍生作品的权利声明
注意:使用本作品进行科研或商业活动需邮箱告知本人详细用途 严禁用于非法用途或倒卖 邮箱:xxy1218594966@gmail.com

本衍生作品（FT-ICR-MS 分子智能分析平台）是基于 CoreMS (https://github.com/EMSL-Computing/CoreMS) 二次开发的软件。

原始 CoreMS 代码的版权归 Battelle Memorial Institute 所有。本衍生作品的作者对其在原始代码基础上进行的修改、新增功能和独立创作的部分享有完整的著作权。


## 3. 致谢

衷心感谢 EMSL-Computing 团队开发的 CoreMS 框架，以及 Battelle Memorial Institute 和 Pacific Northwest National Laboratory (PNNL) 对本项目的支持。特别感谢 CoreMS 核心开发者：Yuri E. Corilo、William Kew、Katherine Heal。
We sincerely thank the EMSL-Computing team for developing the CoreMS framework, and Battelle Memorial Institute and Pacific Northwest National Laboratory (PNNL) for their support. Special thanks to CoreMS core developers: Yuri E. Corilo, William Kew, and Katherine Heal.

## 4. 免责声明

本软件按“原样”提供，不附任何形式的明示或暗示担保。使用本软件所产生的风险由用户自行承担。在任何情况下，版权持有人或贡献者均不对任何损害承担责任。

This software is provided "AS IS" without any warranties, express or implied. Use of this software is at your own risk. In no event shall the copyright holder or contributors be liable for any damages.
