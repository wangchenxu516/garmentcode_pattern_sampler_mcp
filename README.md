## Pattern Sampler MCP

将 GarmentCode 的纸样随机采样器通过 MCP（Model Context Protocol）以 stdio 方式暴露为工具，供任意兼容 MCP 的客户端调用。

- GarmentCode 与数据生成环境参考: [GarmentCode 仓库](https://github.com/maria-korosteleva/GarmentCode?tab=readme-ov-file)
- MCP 协议与客户端使用方式: [MCP 官方文档](https://modelcontextprotocol.io/introduction)

---

## 仓库结构

- `pattern_sampler.py`：核心采样器（在 GarmentCode 环境中运行）
- `pattern_sampler_mcp.py`：MCP 服务器（stdio 传输）
- `run_in_py39.bat`：Windows 启动器（进入 Conda 环境并运行核心脚本）

---

## 一、准备 GarmentCode 核心环境

请严格按照上游仓库搭建 GarmentCode/pygarment 环境（建议 Conda + Python 3.9）：
- 按 `system.template.json` 创建并填写你的 `system.json`（包含 `datasets_path`、`bodies_default_path`、`body_samples_path`、`sim_configs_path` 等）。
- Windows 下 Cairo 依赖：
  - 使用 conda-forge：`conda install -c conda-forge cairo pango gdk-pixbuf cairocffi cairosvg`
  - 或 GarmentCode 自带 DLL（`pygarment/pattern/cairo_dlls`），运行时将该目录加入 PATH（推荐）
- 验证核心能单独运行：
  ```bat
  python pattern_sampler.py --size 1 --name smoke --json_output_path out.json
  type out.json
  ```

---

## 二、MCP 服务器（按照mcp官方文档方式）

MCP 要求服务器通过 stdio 与客户端通信，客户端以“命令 + 参数”方式拉起服务进程。

### 1) 安装依赖（用于运行 MCP 服务的 Python）
按照MCP官方教程，详情请参考教程中的关于创建天气的mcp的例子

### 2) 配置运行所需环境变量（服务启动前）
配置claude_desktop_config.json
- 必须项
  - `GARMENT_RUNNER`：指向启动器（.bat）绝对路径（例如 `D:\pattern_sampler_mcp\run_in_py39.bat`）
  - `PROJECT_DIR`：GarmentCode 工程根目录（例如 `D:\PythonProjects\garmentcode_project`）
  - `CONDA_ENV_PATH`：核心 Conda 环境（例如 `D:\miniconda\envs\py39`）
- 推荐项
  - `TMP_JSON_DIR`：将临时 JSON/任务状态写到项目内的 `tmp`（例如 `D:\PythonProjects\garmentcode_project\tmp`）
  - `GARMENT_TIMEOUT`：子进程超时（秒，建议 `1800`）
  - `DISABLE_GATHER_VISUALS=1`：禁用汇总图片以提速
  - `MAX_RETRIES=20`：减少随机无效参数重试次数
  - `PYTHONUTF8=1`、`PYTHONIOENCODING=UTF-8`：统一编码

或者在 Windows（CMD）里设置：（此为手动调试服务器的备用方案）
```bat
set GARMENT_RUNNER=D:\pattern_sampler_mcp\run_in_py39.bat
set PROJECT_DIR=D:\PythonProjects\garmentcode_project
set CONDA_ENV_PATH=D:\miniconda\envs\py39
set TMP_JSON_DIR=D:\PythonProjects\garmentcode_project\tmp
set GARMENT_TIMEOUT=1800
set DISABLE_GATHER_VISUALS=1
set MAX_RETRIES=20
set PYTHONUTF8=1
set PYTHONIOENCODING=UTF-8
```


## 三、可用工具（服务器导出）

服务器启动后，会导出以下工具供客户端调用：

- 同步（可能客户端侧超时，不推荐长任务）
  - `generate_garments(count: int, garment_type: str = "any", name_prefix: str = "generated")`
    - 返回：`{ success, dataset_path, logs, ... }`

- 异步（推荐）
  - `start_generation(count: int, garment_type: str = "any", name_prefix: str = "generated")`
    - 立即返回：`{ success: true, job_id, status: "queued" }`
  - `get_generation(job_id: str)`
    - 返回：`{ status: queued|running|succeeded|failed, dataset_path?, stdout_tail?, stderr_tail?, ... }`
    - 任务状态会持久化到 `<TMP_JSON_DIR>\jobs\<job_id>.json`，即使服务器/客户端重启也能查询

---

## 五、常见问题与排查

- 任务已生成但客户端超时
  - 使用异步接口（start/get），并将 `GARMENT_TIMEOUT` 设为较大值（如 1800）
- Windows 下缺少 Cairo DLL
  - `conda install -c conda-forge cairo pango gdk-pixbuf cairocffi cairosvg`
  - 或确保 `pygarment\pattern\cairo_dlls` 在 PATH
- 临时 JSON 长时间为 0
  - 设置 `TMP_JSON_DIR` 到项目 `tmp`，并将 `tmp` 与 `datasets` 加入防护软件排除
- CLI 可 5–10 秒结束但通过 MCP 较慢
  - 打开开关：`DISABLE_GATHER_VISUALS=1`、`MAX_RETRIES=20`
  - 确保 `datasets_path` 在 SSD 上，排除实时扫描
- 路径问题（.bat）
  - `.bat` 会 `cd /d "%PROJECT_DIR%"`；确保该目录存在且无隐藏字符

---

## 六、许可与引用

- GarmentCode 环境、数据与示例参考：  
  [GarmentCode 仓库](https://github.com/maria-korosteleva/GarmentCode?tab=readme-ov-file)
  @inproceedings{GarmentCodeData:2024,
  author = {Korosteleva, Maria and Kesdogan, Timur Levent and Kemper, Fabian and Wenninger, Stephan and Koller, Jasmin and Zhang, Yuhan and Botsch, Mario and Sorkine-Hornung, Olga},
  title = {{GarmentCodeData}: A Dataset of 3{D} Made-to-Measure Garments With Sewing Patterns},
  booktitle = {Computer Vision -- ECCV 2024},
  year = {2024},
  keywords = {sewing patterns, garment reconstruction, dataset},
}

@article{GarmentCode2023,
  author = {Korosteleva, Maria and Sorkine-Hornung, Olga},
  title = {{GarmentCode}: Programming Parametric Sewing Patterns},
  year = {2023},
  issue_date = {December 2023},
  publisher = {Association for Computing Machinery},
  address = {New York, NY, USA},
  volume = {42},
  number = {6},
  doi = {10.1145/3618351},
  journal = {ACM Transaction on Graphics},
  note = {SIGGRAPH ASIA 2023 issue},
  numpages = {16},
  keywords = {sewing patterns, garment modeling}
}
- MCP 协议与客户端说明：  
  [MCP 官方文档](https://modelcontextprotocol.io/introduction)
