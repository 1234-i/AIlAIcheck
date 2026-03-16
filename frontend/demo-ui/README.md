# HSE资料AI审查系统（前端）

该前端为 `AllAICheck` 项目提供单页工作台，定位为“新上线系统风格”的审查前端，不是完整产品后台。

- 技术栈：React + Vite + TypeScript
- 页面形态：单页审查工作台
- 对接方式：真实调用后端 `/api/v1` 接口

## 页面模块

1. `资料上传`
- 可选输入项目名称
- 支持多PDF上传
- 展示上传文件列表、文件数量、`batch_id`
- 批次技术信息默认折叠，不占主区域

2. `审查流程`
- 支持单步执行与完整流程执行
- 严格向导顺序：仅允许执行当前步骤
- 每步展示执行状态与耗时

3. `问题清单`
- 调用 `GET /api/v1/batches/{batch_id}/issues?page=1&page_size=50`
- 支持前端筛选风险等级与审查分组
- 支持点击问题查看证据链详情

4. `审查报告`
- 调用 `GET /api/v1/batches/{batch_id}/report`
- 展示摘要、风险分布、问题摘要
- 支持下载 `GET /api/v1/batches/{batch_id}/report.xlsx`

## 本地启动

```bash
cd /Users/wei.lb/Documents/vibecoding/AllAICheck/frontend/demo-ui
npm install
npm run dev
```

默认访问：`http://127.0.0.1:5173`

## 与后端联调

Vite代理配置（`vite.config.ts`）：
- `/api` -> `http://127.0.0.1:8000`

建议先启动后端（联调稳定模式）：

```bash
cd /Users/wei.lb/Documents/vibecoding/AllAICheck
source .venv/bin/activate
LLM_MODE=mock make run
```

## 建议审查顺序

1. 上传资料并创建批次
2. 自动分类
3. 结构化抽取
4. 规则审查
5. 生成报告
6. 查看问题清单
7. 导出Excel报告

## 说明

- 当前后端 `GET /api/v1/batches/{id}` 的 `status` 不随流程更新，前端进度由本地状态机驱动。
- API返回是直接JSON对象，不是统一 envelope。
- 审查结果中的问题描述、整改建议、制程条款内容优先使用后端中文化输出，前端仅做兜底映射。
