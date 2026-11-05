# ellia-pages

静态页面集合。每个页面是一个独立目录，可以单独构建，也可以从仓库根目录全量构建到 `dist/`。

## 目录结构

```text
ellia-pages/
├─ build.py                    # 全站构建入口
├─ dist/                       # 构建输出，已 gitignore
├─ gamejam/
│  ├─ page.toml                # 页面清单
│  ├─ build.py                 # 可选的页面级构建钩子
│  ├─ .gitignore               # 页面本地忽略项
│  ├─ index.html               # 目录页
│  ├─ mirror-2610/
│  │  ├─ index.html            # mirror 主题主页
│  │  ├─ content-field.js      # canvas 背景与上升粒子场
│  │  └─ mirror-lab.html       # mirror.js 实验页
│  ├─ js/
│  │  └─ effects/
│  │     ├─ fade.js            # 逐元素淡入淡出序列
│  │     ├─ mirror.js          # 共享 mirror 效果模块
│  │     └─ parallax.js        # 可复用视差模块（象限页文本）
│  ├─ libs/
│  │  └─ three/
│  │     ├─ three.bundle.js
│  │     ├─ three-bundle-loader.js
│  │     ├─ vendor/
│  │     │  ├─ three.core.js
│  │     │  ├─ three.module.js
│  │     │  └─ three.LICENSE
│  │     └─ src/
│  │        └─ three-bundle-entry.js   # esbuild 输入，不发布
│  └─ tools/                   # 测试/工具脚本，不进入 dist
└─ openspec/
```

`mirror-2610/index.html` 使用 `js/effects/mirror.js`、`js/effects/fade.js`、`js/effects/parallax.js` 和共享 three loader；启动时先加载 three，再预检 HTML-in-Canvas 并选择 WebGL / SVG 后端。`libs/three/` 由 mirror lab 和后续 WebGL 页面共享；`parallax.js` 挂载在象限页的文本层上。

目录页 `gamejam/index.html` 是一个独立的 Material 3 风格首页，支持切换 seed color；只在“页面”区展示 `MIRROR / 2610`，`mirror-lab.html` 保留为直接访问的诊断页面，不列入目录页。

当前页面规格记录在 [gamejam/openspec/specs/gamejam/spec.md](gamejam/openspec/specs/gamejam/spec.md)。

`mirror-2610/` 的启动流程：

1. 先用 `three-bundle-loader.js` 加载 `three.bundle.js`，显示下载进度。
2. 加载完成后运行 `checkHtmlInCanvasSupport()`。
3. 支持且版本兼容：直接使用 WebGL 后端。
4. 支持但版本不兼容或无法识别：在加载层内显示方框面板，让用户选择继续 WebGL 或回退 SVG。
5. 不支持 HTML-in-Canvas：自动回退 SVG，并在加载层内提示可换用兼容 Chrome 并启用实验特性。
6. 加载层使用白底黑字、无圆角方框；加载层与预检面板都居中。预检出现时加载进度淡出、面板淡入（250ms），最终加载层以 250ms 淡出；在预检面板被回答或关闭前，加载层不会移除。
7. 内容区宽高各为页面的 72%；`mirror.js` 的共享 `_relayout()` 统一把内容矩形量化到整数设备像素，误差小于 1 个 CSS 像素。
8. 内容区包含一个嵌套 Canvas 2D canvas（`content-field.js`）和一个四页幻灯片 deck：canvas 每帧填充实心 `center` 色并绘制从底部上升的暗色粒子；deck 直接位于 `#art` 内，因此文字、标题和分隔线都会参与镜像。canvas 不是 drawable 根，使用 `devicePixelRatio` 上限 2 的 backing store，不使用 CSS transform/filter。
9. 内容场第一帧渲染完成后才移除加载层；Canvas 2D 不可用时保留静态 `center` 色背景并跳过粒子场，deck 仍正常显示，mirror 仍正常挂载。
10. WebGL 默认使用 `renderScale: 1` 的 direct pass，镜像和中心内容在同一 1x pass 中完成，不再产生 0.5x 合成缝。低于 1 的 composite 路径仍保留：它使用 2 device px full-res edge skirt，用 body 纹理边缘像素覆盖低分辨率上采样缝。DOM seam guard 已移除。

### 内容场

`mirror-2610/content-field.js` 用 Canvas 2D 绘制实心背景和上升粒子。

- **实心背景**：内容背景只有 `center` 色；没有深度带、渐变、矩形环、内开口线或 CSS 边框。mirror root 使用同一个 `center` 色；只有在 composite 模式下，WebGL 才使用 full-res edge skirt 重复 content 的真实边缘颜色。
- **上升粒子**：固定大小的粒子池按内容面积生成（面积 / 7000，限制在 24–120 个）。每个粒子的尺寸、深浅、速度、横向摆动和寿命独立随机；粒子从内容底部缓慢上升，随时间缩小并淡出，结束后回到底部重新淡入。初始化时粒子生命进度被均匀预热，首帧就有完整分布。
- **绘制方式**：粒子用预生成的径向渐变 sprite 画柔和边缘，再叠一个小实心核心；粒子颜色随 `Particle` 调参实时重建 sprite。
- **运行节奏**：只要页面可见，rAF 就一直运行；鼠标停住、移出内容或完全不动都不会暂停。页面隐藏时停止，恢复可见时继续。`prefers-reduced-motion` 下只渲染一帧静态分布，不启动循环。
- **固定参数**：粒子尺寸 `1.2–4.2px`、速度 `16–38px/s`、密度面积 `7000px²`、DPR 上限 `2`；`Copy config` 的 `particles` 段会报告这些值和当前数量。
- **固定 feather**：两个后端都固定为 `72px`，面板只显示只读值，不提供调节。
- **验证环境**：推荐使用 Chrome Beta 158 验证 WebGL。Chrome 155 等低于 157 的版本存在嵌套 canvas 的 device-pixel 缩放问题，页面会按现有预检提示并默认回退 SVG。

### 幻灯片 deck

内容区是一个四页的静态 deck，直接在 `#art` 内参与镜像。页面不再渲染之前的 `FIELD / SPECIMEN / INDEX / NODE` 占位容器。

- **四页内容**：封面、`象限`、`排行榜`、`信息`。封面左下是 `CEA GameJam` 与较小的 `2026.10` 同一基线，下一行是 `参赛作品展示`；右下是空的 `ellia / sideview` 三角形占位；最底部有一条 3px 黑边。第二页是四象限布局；第三页用两条竖线夹住可滚动队伍列表；`信息` 保留 eyebrow、标题、说明文字和 footer。
- **视觉规则**：黑字、透明背景、无圆角、等宽大写标签；封面不使用 header/footer 分隔线，文字也不带任何边框，全部为衬线体、左对齐；线稿只有右下角 2px 的三角占位和底部 3px 黑边。第二页同样不设 eyebrow/footer，以 3px 中心十字和四个无外框的象限文本构成版面。
- **翻页**：顶部左右角两个 40×34px 的方框按钮，只显示箭头，不参与镜像；滚轮、方向键、`PageUp`/`PageDown`、`Home`/`End` 也可切换。
- **全页指针圆环**：保留原生光标；封面、象限、排行榜、信息四页的内容区都会在指针周围绘制浅灰圆环（`#9d9d9d`）。圆环是 deck 的直接子层，位于所有 slide 之下，因此在象限页仍会被四色滤镜着色；尺寸和描边随指针速度变化。
- **持久规则条**：封面底部黑边由两条重叠的纯色 `absolute` div 组成，位于 deck 层、所有 slide 之下，不受淡入淡出影响；超出 content 的部分由 `#deck` 的 `overflow:hidden` 自然裁切。两条线的长度取内容宽高的两倍，旋转和移动过程中两端始终在内容外，避免看到线头。进入第二页时，一条平移到内容中心高度，另一条 `rotate(90deg)`，两者以 `720ms` transition 组成 3px 中心十字；进入第三页时分成 20% / 80% 两根竖线，夹住 60% 宽的排行榜；返回封面时还原。第二页原有的分隔线 DOM 已移除。
- **逐元素淡入淡出**：`js/effects/fade.js` 读取元素上的 `data-fade`、`data-fade-in-delay`、`data-fade-out-delay`（毫秒），用 Web Animations 逐个执行 opacity 动画，基础时长 `220ms`。
- **当前排版节奏**：封面按 `CEA GameJam` → `2026.10` → `参赛作品展示` → 三角占位依次进入，持久规则条不参与淡入淡出；象限页按四个象限文本 → 中心 `镜` 依次进入；排行榜按左侧标题 → 队伍列表 → 右侧标题进入；`信息` 按 kicker → 标题 → 正文 → 信息行 → footer 依次进入。离开时使用更短的独立延迟。整组动画结束后才解锁翻页。`prefers-reduced-motion` 下直接切换。
- **文本间隙**：品牌与日期同一基线，行内间距约 `16–32px`；品牌/日期行与 `参赛作品展示` 之间约 `16–34px`。左文本与右占位之间使用固定响应式列距（约 `24–58px`），避免两列贴在一起。
- **布局**：`cqw`/`cqh` 相对内容尺寸；封面分为左文本、右占位两列，底对齐。`--cover-bar-height` 控制底部黑边高度（默认 `3px`）；`--cover-bottom-gap` 固定为 `32px`，`--cover-text-y` 固定为 `0px`；只有 `--cover-art-y` 用来移动占位。三角描边固定 `2px`；窄屏改为单列，占位放到文本下方并靠右。
- **配置**：`Copy config` 的 `deck` 段报告页数、当前页、`fadeDuration`、`fadeMode` 和 fade 元素数量；`cover` 段报告 `barHeight`、`bottomGap`、`textY`、`imageY`；`parallax` 段报告当前深度层，`quadrants` 段报告悬停象限、滤镜面板和圆环尺寸/速度参数。
- **已知问题**：Chrome Beta 的 WebGL 侧边镜像在切页后可能保留上一页的 DOM 残影；中心 content 和翻页状态正常。这是 HTML-in-Canvas 捕获记录刷新的问题，后续需要单独处理 `mirror.js` 的纹理刷新。

### 象限页

第二页（`data-slide="1"`）以页面中心为原点分成四个象限：左上 `时间`、右上 `主题`、左下 `限制`、右下 `评分`，中心是单独的 `镜`。

- **分隔线与外框**：中心横/竖分隔线为 `3px`；四个象限的标题和正文不再带矩形外框。每个文本组从象限中心向对应的外角偏移：水平约内容宽度的 `6%`，垂直约 `5.2%`（窄屏降到 `2.4%`），让中心更空。中心 `镜` 也不再带任何外框，保持单独的字形。
- **SVG 背板滤镜**：四个透明面板分别覆盖四个象限，使用 `backdrop-filter: url(#…)`。左上红 `#ff2b2b`、右上绿 `#00c853`、左下蓝 `#1f52ff`，都用 `feFlood + feBlend mode="screen"` 将深色墨迹推向对应颜色；白色在 screen 下保持白色，越深的像素着色越明显。右下用 `feColorMatrix saturate=0` 直接去饱和。颜色是高饱和混色，不是把每个像素强制替换成纯原色。四个面板带 `data-fade`，进入/离开第二页时以 `opacity` 跟随切页淡入淡出（`220ms`）；SVG filter URL 本身不做插值。
- **指针着色**：圆环位于四个滤镜面板下方，因此跨象限时会被对应颜色重新着色；中心没有方框，圆环会继续显示在 `镜` 字下方。原生光标始终可见，移出内容或进入按钮/调参面板时圆环隐藏。
- **圆环速度响应**：全页圆环共用同一套速度响应。静止或慢速时直径约 `34px`、描边约 `5.5px`；速度升高时直径增大到约 `82px`，描边减薄到约 `1.1px`。速度值经过平滑和衰减，停止后圆环回到小而厚；位置本身直接贴住指针。
- **悬停内容**：每个象限默认只显示衬线标题；指针移入后标题淡出，显示多行衬线正文，必要时自动换行。中心 `镜` 周围保留一块不可见死区，不触发象限悬停。中心 `镜` 位于四个滤镜下方，因此字会被红/绿/蓝/灰按象限切开着色。
- **字号**：第二页字号约为初版的 `1.5` 倍。桌面标题 `40.5–75px`、正文 `21–28.5px`、中心 `镜` `93–162px`；窄屏为 `27–45px`、`13.5–18px`、`60–96px`。
- **文本视差**：`parallax.js` 挂载在象限页文本和排行榜上。象限标题深度 `0.22`、正文深度 `0.5`、中心 `镜` 深度 `0.9`；排行榜容器 `0.18`、卡片基础 `0.28`、悬浮卡片提升到 `0.68`；桌面最大位移 `24px`，窄屏按视口宽度缩放（最小 `8px`），模块自身再做平滑。
- **性能与后端**：四个背景滤镜会随粒子场和指针持续重绘；WebGL 与 SVG 后端都验证了滤镜、指针和镜像输出。

### 排行榜页

第三页（`data-slide="2"`）用两条竖线夹住中央排行榜：左侧竖排 `评分结果`，右侧竖排 `Rank list`，中间是可独立上下滚动的队伍列表。

- **框架**：两条持久规则条进入第三页后旋转成竖线，位于内容宽的 `20%` 与 `80%`，中央列宽 `60%`；列表容器左右各留 `6–14px` 外边距，滚动条不会贴住竖线；窄屏隐藏两侧文字，规则移到 `4%` / `96%`，列表占 `92%`。
- **滚动轴**：排行榜 slide 设为 `overflow:visible`；列表 `overflow-x:hidden` 禁止横向滚动条，`overflow-y:auto` 保留纵向滚动。左右 padding 预留 `14–26px`，足够容纳卡片放大和 parallax 位移，避免横向裁切可见内容。外层 mirror content（`#art` / `#deck`）继续 `overflow:hidden`，负责内容边界的镜像裁切。
- **队伍卡片**：12 个占位队伍，透明背景、1px 黑框；每张卡包含编号、队名、成员占位和得分，列表上下滚动。
- **滚动优先**：指针位于两条竖线之间时，window 捕获阶段的 wheel 处理器把滚动量累加到目标值，再用 rAF + 指数插值推进 `scrollTop`，并 `preventDefault` / `stopPropagation`；不再依赖事件最终落在哪个卡片或 DOM 上，也不会触发 deck 翻页。原生滚动、滚动条拖动或键盘操作会中断插值并重新同步目标值。`prefers-reduced-motion` 下直接跳转。离开该区域后恢复翻页。
- **悬浮**：卡片使用 `scale` 放大到 `1.035`，不加白底；仅保留 1px 描边。卡片基础视差深度 `0.28`，悬浮时切到 `0.68`，离开后恢复；排行榜容器自身深度 `0.18`。卡片不再可聚焦，点击透明区域不会保留“选中”层级。
- **尺寸**：桌面卡片宽约 `530px`、最小高度约 `80px`；窄屏改为单列列表。

### Resize 结构遮盖层

页面顶部有一层全屏的构成主义结构图，`z-index:78`，位于 deck 控件之上、启动层之下，不参与镜像，也不拦截指针。

- **触发**：监听 `mirror` 的 resize 生命周期——`resizeStart` 淡入、`resizing` 保持并更新尺寸、`resizeEnd` 后排定淡出。单独的 `resize` 事件只用来更新读数/尺寸，不再触发显示，因此 `mirror.refresh()` 和封面调参不会误触发遮盖层。初始挂载阶段不显示；启动层移除后才启用。mirror 的 resize 去重窗口为 `500ms`。
- **节奏**：`resizeStart` 时以 `500ms` 淡入；持续 resize 期间保持；`resizeEnd` 后保持约 `950ms`，再以 `500ms` 淡出。
- **内容**：白底、细黑外框；按 mirror 区域划分为中央 content 矩形和上、下、左、右四条反射带；中央矩形上方和左侧各有一条带端点的尺寸线，实时显示内容 CSS 宽高；右下角显示 `resizing...`。四个反射带和中心分别用淡灰英文衬线标签标识，不加网格、斜线或额外图形。
- **尺寸更新**：`resizeStart` 开启一个 rAF 测量循环，在 resize 生命周期内每帧用容器当前宽高调用 `mirror.previewLayout(width, height)`，即时解析 `72%` 内容尺寸并更新标注；`resizing` 事件也会刷新。它不依赖 debounce 后才落地的 `#art` 矩形，`resizeEnd` 停止循环并用真实矩形收口。
- **降级**：`prefers-reduced-motion` 下改为直接显示/隐藏。

实现位于 `mirror-2610/index.html` 的 `#structureVeil`、`showStructureVeil()` 和 `hideStructureVeilSoon()`。

### 设备像素布局

`mirror.js` 的 `_relayout()` 生成统一的 layout：

```js
{
  width, height, ax, ay, aw, ah,  // CSS px
  dpr,
  device: { width, height, ax, ay, aw, ah } // integer device px
}
```

SVG filter、WebGL canvas/render target、纹理捕获和 hit testing 都从同一份 `device` 数据派生。页面只传入 `contentSize: { width: '72%', height: '72%' }`，不再自行做 DPR 取整。

WebGL 默认走 1x direct 路径；`renderScale < 1` 时仍可走 composite 路径：低分辨率镜像 target + 1x body target，最后用 linear upscale 合成。合成阶段额外绘制一圈 2 device px 的 full-res edge skirt，UV 取 body 纹理边缘内侧 1.5 texel，用真实边缘颜色盖住 low-res 边界。

### 调参面板

`mirror-2610/index.html` 右下角有一个悬浮 `TUNE / 2610` 面板，默认折叠：

- 调整 `Particle`（粒子颜色，默认 `#242622`）和 `Center`（实心背景）颜色；直接更新 canvas，不重建 mirror
- 调整封面 `Line`（底部黑边高度，默认 `3px`）和 `Image Y`（占位垂直位移，默认 `0px`）；`Gap` 固定 `32px`、`Text Y` 固定 `0px`，面板只显示只读值。`Line` / `Image Y` 写入 `--cover-bar-height` / `--cover-art-y`，固定值写入 `--cover-bottom-gap` / `--cover-text-y`；封面 `Line` 只影响底部黑边，第二页十字固定 `3px`；三角描边固定 `2px`
- 固定 feather `72px`（两个后端一致）；面板只显示只读值，不提供调节
- 固定参数不开放调整：blur `2.00`；WebGL `renderScale 1` / `contentScale 1`；SVG `mapScale 0.1` / `maxMR 1920x1080`
- 显示 DPR、内容 CSS 尺寸、内容设备像素、canvas 输出尺寸
- 支持 `Copy config` 和 `Reset`；`Copy config` 额外报告粒子参数、当前数量、deck 的逐元素 fade 配置、封面占位/间距/位移、象限滤镜/指针和文本视差层级
- 可调参数保存在 `localStorage`

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
   ├─ mirror-2610/
   │  ├─ index.html
   │  ├─ content-field.js
   │  └─ mirror-lab.html
   ├─ js/
   │  └─ effects/
   │     └─ mirror.js
   └─ libs/
      └─ three/
         ├─ three.bundle.js
         ├─ three-bundle-loader.js
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
title = "ELLIA PAGES — GAMEJAM 2026"
entry = "index.html"      # 构建后必须存在，且必须被 include 命中

include = [
  "index.html",
  "mirror-2610/**",
  "js/effects/**",
  "libs/three/**",
]

exclude = [
  "libs/three/src/**",
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

构建系统不负责启动服务器。开发时直接服务 `gamejam` 源码目录：

```powershell
.\.venv\Scripts\python.exe -m http.server 4173 --directory gamejam
```

- 页面目录：<http://127.0.0.1:4173/>
- mirror 主页：<http://127.0.0.1:4173/mirror-2610/>
- mirror 实验页：<http://127.0.0.1:4173/mirror-2610/mirror-lab.html>
- 构建产物预览：把 `--directory` 改为 `dist/gamejam`，并换一个端口。

页面测试脚本：

```powershell
.\.venv\Scripts\python.exe gamejam\tools\verify_render_scale.py
.\.venv\Scripts\python.exe gamejam\tools\verify_resize_hooks.py
.\.venv\Scripts\python.exe gamejam\tools\probe_mouse_fx_lab.py

# 内容场（粒子/双后端/DPR/减少动态/回退）
.\.venv\Scripts\python.exe gamejam\tools\probe_content_field.py

# 幻灯片 deck（翻页/淡入淡出/双后端/移动端）
.\.venv\Scripts\python.exe gamejam\tools\probe_deck.py
```

前三个脚本默认访问 `http://127.0.0.1:4173/mirror-2610/mirror-lab.html`；内容场和 deck 探测访问 `http://127.0.0.1:4173/mirror-2610/`，默认使用 Chrome Beta。

## three 运行时 bundle

`gamejam/libs/three/three.bundle.js` 是生成文件，正常构建直接复制它，不需要 Node。修改入口或 vendor 后重新生成：

```powershell
.\gamejam\tools\build-three-bundle.ps1
```

该脚本使用 `npx esbuild@0.25.0`，首次运行需要 Node/npm 和网络。页面构建钩子会在 `libs/three/src/three-bundle-entry.js` 比 bundle 新时给出警告。

## 素材重绘

`gamejam/assets/mirror-26/ellia-sideview.svg` 由同目录的 PNG 重绘而来，是白底、双灰披风、近黑人物和深红缎带的五色分层 SVG。生成脚本：

```powershell
.\.venv\Scripts\python.exe gamejam\tools\trace_sideview.py
```

脚本只使用标准库完成 PNG 解码、调色板分层、灰边/杂点清理、Taubin 轮廓平滑和 Bézier 拟合；目标是流畅的矢量线条，而不是逐像素描边。`--flow` 控制轮廓平滑强度（灰色布料默认是人物层的两倍），`--epsilon` / `--tolerance` 控制简化与拟合误差，`--stroke` 用来补层与层之间的亚像素缝隙。

`--render` / `--diff` 会额外使用 Playwright + Chrome Beta 渲染预览并报告逐层 IoU：

```powershell
.\.venv\Scripts\python.exe gamejam\tools\trace_sideview.py --render .dsh/ellia-preview.png --diff .dsh/ellia-diff.png
```

## 手动描改器

`gamejam/tools/trace-editor.html` 是一个不依赖构建的 SVG 描改页面：钢笔点击/拖拽画贝塞尔曲线，点回起点闭合后按当前颜色填充；参考 PNG 可调透明度、正片叠底和置顶；支持图层、撤销/重做、localStorage 草稿、JSON 工程与 SVG 导出。

用现有的开发服务器打开即可（页面通过相对路径读取 `assets/mirror-26/ellia-sideview.png`）：

```powershell
.\.venv\Scripts\python.exe -m http.server 4173 --directory gamejam
```

<http://127.0.0.1:4173/tools/trace-editor.html>

操作要点：

- `P` 钢笔：点击加点，按住拖动拉出对称切线；点回第一个点闭合，`Enter` 结束，`Esc` 放弃当前路径。
- `V` 选择：拖动节点/控制柄；双击线段插入节点；双击节点切换尖角/平滑；`Delete` 删除；方向键微移。
- `Space` + 拖动平移，滚轮缩放，`F` 适配窗口，`H` 隐藏参考图，`1–5` 快速换色。
- 钢笔模式下色板只决定**下一个区域**的颜色；选择模式下点色板才会改当前选中区域。已闭合区域也可以在右侧属性面板改色、填充规则和层级。
- 右侧“参考图”支持透明度、正片叠底（白底透出棋盘格）和置顶；在已填区域上继续描时建议勾选置顶，或把正片叠底关掉。
- 草稿自动保存在浏览器 localStorage；“导出 SVG”可以带白底或透明；编辑器节点、控制柄、选中线不会进入导出。

## 为什么使用 Python

- 页面都是静态文件，构建主要是校验、复制和少量页面钩子；Python 标准库足够。
- 仓库里的浏览器测试和探测脚本已经是 Python，构建与测试共用同一个运行环境。
- 不需要为普通构建引入 `node_modules`、包管理器或前端框架。
- 只有 three bundle 需要 esbuild；它被隔离在 `gamejam/tools/build-three-bundle.ps1`，不影响日常构建。

如果以后需要资源指纹、HTML 压缩或真正的 JS 打包，可以在现有入口上增加步骤，或再引入 Vite/Astro；目前没有必要。
