# ellia-pages

静态页面集合。每个页面是一个独立目录，可以单独构建，也可以从仓库根目录全量构建到 `dist/`。

## 目录结构

```text
ellia-pages/
├─ build.py                 # 全站构建入口
├─ dist/                    # 构建输出，已 gitignore
├─ gamejam/
│  ├─ page.toml             # 页面清单
│  ├─ build.py              # 可选的页面级构建钩子
│  ├─ .gitignore            # 页面本地忽略项
│  ├─ index.html
│  ├─ mirror-lab.html
│  ├─ js/
│  └─ tools/                # 测试/工具脚本，不进入 dist
└─ openspec/
```

## 构建

要求 Python 3.11+，只使用标准库，不需要安装额外依赖。

```powershell
# 查看页面列表
python build.py --list

# 全量构建到 dist/
python build.py

# 只构建一个页面
python build.py gamejam

# 构建并显示细节；把页面 warning 当作错误
python build.py gamejam --strict --verbose

# 先清空 dist/ 再全量构建（可清理已删除页面的残留）
python build.py --clean
```

也可以显式使用虚拟环境：

```powershell
.\.venv\Scripts\python.exe build.py
```

输出结构：

```text
dist/
└─ gamejam/
   ├─ index.html
   ├─ mirror-lab.html
   └─ js/
      ├─ mirror.js
      ├─ three-bundle-loader.js
      ├─ three.bundle.js
      └─ vendor/
```

构建行为：

- `dist/<page>/` 会以 staging 目录整体替换，不会留下上一次构建的旧文件。
- 单个页面构建失败时，不会替换已有的 `dist/<page>/`。
- 默认只保证当前构建的页面目录是干净的；要删除已移除页面的残留，使用 `--clean`。
- `--out DIR` 可修改输出目录，但会拒绝项目根目录、页面源码目录以及 `.git/`、`.venv/` 等保留目录。
- 当前构建只做复制和校验，不做 HTML/CSS/JS 压缩或指纹化。

## 页面清单 `page.toml`

```toml
name = "gamejam"          # 必须与目录名一致
title = "GAMEJAM 2026"
entry = "index.html"      # 构建后必须存在，且必须被 include 命中

include = [
  "index.html",
  "mirror-lab.html",
  "js/**",
]

exclude = [
  "js/three-bundle-entry.js",
]
```

- `include` 是必需项，相对于页面目录，支持 `*`、`**` 等 glob。
- 目录被 glob 命中时会递归收集其中的文件。
- `exclude` 使用 `fnmatch` 匹配相对于页面目录的路径。
- `page.toml`、页面 `build.py`、`.gitignore` 和 `tools/` 不会自动进入构建，除非被 `include` 明确包含。
- 当前 `gamejam/build.py` 会额外检查并阻止这些源码文件泄漏到 `dist/`。

## 页面级 `build.py`

页面目录内的 `build.py` 是可选的，由根目录 `build.py` 动态导入。它不会被复制到 `dist/`。

可定义两个钩子：

```python
def prebuild(ctx):
    """复制前执行，用于校验源文件或补齐构建输入。"""

def postbuild(ctx):
    """复制完成后执行，可修改 staging 目录。"""
```

`ctx` 提供：

- `ctx.page`：页面元数据（`slug`、`entry` 等）
- `ctx.source`：页面源码目录
- `ctx.stage`：本次构建的 staging 目录
- `ctx.out_root`：输出根目录
- `ctx.strict` / `ctx.verbose`
- `ctx.log(message)`：仅在 `--verbose` 时输出
- `ctx.warn(message)`：记录警告；配合 `--strict` 会使构建失败

钩子抛出异常会终止该页面的构建，并保留旧的 `dist/<page>/`。当前 `gamejam/build.py` 会检查 three 运行时文件、检测过期的 `three.bundle.js`，并防止源码文件进入产物。

## 新增页面

1. 在仓库根目录创建页面目录，例如 `new-page/`。
2. 添加 `new-page/page.toml`，至少包含 `name`、`entry` 和 `include`。
3. 需要额外校验时添加 `new-page/build.py`。
4. 添加 `new-page/.gitignore`，忽略页面本地日志、缓存和临时产物。
5. 运行 `python build.py --list` 确认发现，再运行 `python build.py new-page`。

## 开发服务器

构建系统不负责启动服务器。开发时直接服务页面源码目录：

```powershell
.\.venv\Scripts\python.exe -m http.server 4173 --directory gamejam
```

- 源码预览：<http://127.0.0.1:4173/mirror-lab.html>
- 构建产物预览：把 `--directory` 改为 `dist/gamejam`，并换一个端口。

页面测试脚本：

```powershell
.\.venv\Scripts\python.exe gamejam\tools\verify_render_scale.py
.\.venv\Scripts\python.exe gamejam\tools\verify_resize_hooks.py
.\.venv\Scripts\python.exe gamejam\tools\probe_mouse_fx_lab.py
```

这些脚本默认访问 `http://127.0.0.1:4173/mirror-lab.html`。

## three 运行时 bundle

`gamejam/js/three.bundle.js` 是生成文件，正常构建直接复制它，不需要 Node。修改 three 入口或 vendor 后重新生成：

```powershell
.\gamejam\tools\build-three-bundle.ps1
```

该脚本使用 `npx esbuild@0.25.0`，首次运行需要 Node/npm 和网络。页面构建钩子会在 `three-bundle-entry.js` 比 bundle 新时给出警告。

## 为什么使用 Python

- 页面都是静态文件，构建主要是校验、复制和少量页面钩子；Python 标准库足够。
- 仓库里的浏览器测试和探测脚本已经是 Python，构建与测试共用同一个运行环境。
- 不需要为普通构建引入 `node_modules`、包管理器或前端框架。
- 只有 three bundle 需要 esbuild；它被隔离在 `gamejam/tools/build-three-bundle.ps1`，不影响日常构建。

如果以后需要资源指纹、HTML 压缩或真正的 JS 打包，可以在现有入口上增加步骤，或再引入 Vite/Astro；目前没有必要。
